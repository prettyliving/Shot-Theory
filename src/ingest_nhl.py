"""Shot Theory: load NHL game data into PostgreSQL.

Usage:
    python src/ingest_nhl.py --start 2025-10-07 --end 2025-10-20
    python src/ingest_nhl.py --start 2025-10-07 --end 2026-04-20 --dsn postgresql://localhost/shot_theory

Raw JSON responses are cached in data/raw/ so re-runs don't re-hit the API.
Source: the NHL's public web API (api-web.nhle.com). It is unofficial and
undocumented, so field names may change; the parsers below use .get() defensively.
"""
import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import psycopg
import requests

BASE = "https://api-web.nhle.com/v1"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
FINAL_STATES = {"FINAL", "OFF"}


def get_json(path: str, cache_name: str):
    """GET an API path, caching the response on disk."""
    cache = RAW / cache_name
    if cache.exists():
        return json.loads(cache.read_text())
    resp = requests.get(f"{BASE}/{path}", timeout=30)
    resp.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(resp.text)
    time.sleep(0.25)  # be polite
    return resp.json()


def mmss_to_seconds(s):
    if not s or ":" not in s:
        return None
    m, sec = s.split(":")
    return int(m) * 60 + int(sec)


def name(obj):
    return (obj or {}).get("default") if isinstance(obj, dict) else obj


# ---------- discovery ----------
def list_final_games(start: date, end: date):
    """Walk the weekly schedule and return final games (types 2/3) in range."""
    games, cursor = {}, start
    while cursor <= end:
        wk = get_json(f"schedule/{cursor.isoformat()}", f"schedule/{cursor.isoformat()}.json")
        for day in wk.get("gameWeek", []):
            for g in day.get("games", []):
                d = datetime.strptime(day["date"], "%Y-%m-%d").date()
                if start <= d <= end and g.get("gameType") in (2, 3) and g.get("gameState") in FINAL_STATES:
                    games[g["id"]] = g
        nxt = wk.get("nextStartDate")
        cursor = datetime.strptime(nxt, "%Y-%m-%d").date() if nxt else cursor + timedelta(days=7)
    return list(games.values())


def upsert_team(cur, t):
    """Team ids/abbrevs come from the boxscore; conference/division are filled in afterwards."""
    full = " ".join(filter(None, [name(t.get("placeName")), name(t.get("commonName"))])) or t.get("abbrev")
    cur.execute(
        """INSERT INTO teams (team_id, abbrev, name) VALUES (%s,%s,%s)
           ON CONFLICT (team_id) DO NOTHING""",
        (t["id"], t["abbrev"], full),
    )


def fill_team_divisions(cur):
    st = get_json("standings/now", "standings_now.json")
    for t in st.get("standings", []):
        cur.execute(
            "UPDATE teams SET conference=%s, division=%s WHERE abbrev=%s",
            (t.get("conferenceName"), t.get("divisionName"), name(t.get("teamAbbrev"))),
        )


# ---------- per game ----------
def load_game(cur, g):
    gid = g["id"]
    box = get_json(f"gamecenter/{gid}/boxscore", f"boxscore/{gid}.json")
    pbp = get_json(f"gamecenter/{gid}/play-by-play", f"pbp/{gid}.json")

    home, away = box["homeTeam"], box["awayTeam"]
    upsert_team(cur, home)
    upsert_team(cur, away)
    last = (box.get("gameOutcome") or {}).get("lastPeriodType", "REG")
    cur.execute(
        """INSERT INTO games (game_id, season, game_type, game_date, home_team_id, away_team_id,
                              home_score, away_score, ended_in)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (game_id) DO NOTHING""",
        (gid, box["season"], box["gameType"], box["gameDate"], home["id"], away["id"],
         home.get("score"), away.get("score"), last),
    )

    # team-level rows (derived from boxscore + play-by-play)
    pim = {home["id"]: 0, away["id"]: 0}
    for p in pbp.get("plays", []):
        if p.get("typeDescKey") == "penalty":
            d = p.get("details", {})
            if d.get("eventOwnerTeamId") in pim:
                pim[d["eventOwnerTeamId"]] += d.get("duration") or 0
    for me, opp, is_home in ((home, away, True), (away, home, False)):
        gf, ga = me.get("score", 0), opp.get("score", 0)
        won = gf > ga
        result = "W" if won else ("L" if last == "REG" else "OTL")
        cur.execute(
            """INSERT INTO team_game_stats (game_id, team_id, opponent_id, is_home, goals_for, goals_against,
                                            shots_for, shots_against, pim, result, standings_pts)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (gid, me["id"], opp["id"], is_home, gf, ga, me.get("sog"), opp.get("sog"),
             pim[me["id"]], result, 2 if won else (0 if result == "L" else 1)),
        )

    # players (skaters only; goalie tables are a later phase)
    stats = box.get("playerByGameStats", {})
    for side, team in (("homeTeam", home), ("awayTeam", away)):
        for grp in ("forwards", "defense"):
            for p in stats.get(side, {}).get(grp, []):
                pname = name(p.get("name")) or ""
                first, _, last_n = pname.partition(" ")
                cur.execute(
                    """INSERT INTO players (player_id, first_name, last_name, position)
                       VALUES (%s,%s,%s,%s) ON CONFLICT (player_id) DO NOTHING""",
                    (p["playerId"], first, last_n, p.get("position")),
                )
                cur.execute(
                    """INSERT INTO player_game_stats (game_id, player_id, team_id, position, goals, assists,
                           points, shots, toi_seconds, pim, plus_minus, hits, blocked_shots, pp_goals,
                           takeaways, giveaways)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (gid, p["playerId"], team["id"], p.get("position"), p.get("goals", 0), p.get("assists", 0),
                     p.get("points", 0), p.get("sog", 0), mmss_to_seconds(p.get("toi")), p.get("pim", 0),
                     p.get("plusMinus"), p.get("hits"), p.get("blockedShots"), p.get("powerPlayGoals", 0),
                     p.get("takeaways"), p.get("giveaways")),
                )

    # events
    for p in pbp.get("plays", []):
        kind, d = p.get("typeDescKey"), p.get("details", {})
        period = (p.get("periodDescriptor") or {}).get("number")
        if kind == "goal":
            cur.execute(
                """INSERT INTO goals (game_id, period, time_in_period, team_id, scorer_id, assist1_id,
                                      assist2_id, strength, empty_net, shot_type, x_coord, y_coord)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (gid, period, p.get("timeInPeriod"), d.get("eventOwnerTeamId"), d.get("scoringPlayerId"),
                 d.get("assist1PlayerId"), d.get("assist2PlayerId"), strength(p, d, home["id"]),
                 empty_net(p, d, home["id"]), d.get("shotType"), d.get("xCoord"), d.get("yCoord")),
            )
        elif kind == "penalty":
            cur.execute(
                """INSERT INTO penalties (game_id, period, time_in_period, team_id, player_id,
                                          description, severity, minutes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (gid, period, p.get("timeInPeriod"), d.get("eventOwnerTeamId"), d.get("committedByPlayerId"),
                 d.get("descKey"), d.get("typeCode"), d.get("duration")),
            )


def _situation(p):
    """situationCode digits: away goalie, away skaters, home skaters, home goalie."""
    code = str(p.get("situationCode", ""))
    return [int(c) for c in code] if len(code) == 4 and code.isdigit() else None


def strength(p, d, home_id):
    s = _situation(p)
    if not s:
        return None
    ag, ask, hsk, hg = s
    return f"{hsk}v{ask}" if d.get("eventOwnerTeamId") == home_id else f"{ask}v{hsk}"


def empty_net(p, d, home_id):
    s = _situation(p)
    if not s:
        return None
    ag, ask, hsk, hg = s
    return (ag == 0) if d.get("eventOwnerTeamId") == home_id else (hg == 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=date.fromisoformat)
    ap.add_argument("--end", required=True, type=date.fromisoformat)
    ap.add_argument("--dsn", default="postgresql://localhost/shot_theory")
    args = ap.parse_args()

    games = list_final_games(args.start, args.end)
    print(f"{len(games)} final games between {args.start} and {args.end}")
    with psycopg.connect(args.dsn) as conn, conn.cursor() as cur:
        for i, g in enumerate(sorted(games, key=lambda x: x["id"]), 1):
            load_game(cur, g)
            if i % 25 == 0:
                conn.commit()
                print(f"  loaded {i}/{len(games)}")
        fill_team_divisions(cur)
        conn.commit()
    print("done")


if __name__ == "__main__":
    main()
