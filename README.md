# Shot Theory

**Hockey performance analytics built on real NHL data.**

Shot Theory asks one question: *what can hockey data tell us about what drives team and player success?*
It is a standalone project, separate from PULSE (business intelligence). This one is about sports performance.

## Analysis questions

**Team**
1. Which teams generate the most offense, and how much of that is shot volume vs. finishing?
2. How does home performance compare with away?
3. How strongly does shot volume relate to winning?
4. What changes during winning and losing streaks?

**Player**
5. How does production change over a season?
6. Which players are consistently productive? (see `docs/definitions.md`)

## Stack
PostgreSQL · Python (pandas, statsmodels, matplotlib) · Power BI

## Project layout
```
sql/            schema and analysis queries
src/            ingestion code
notebooks/      exploration and statistics
dashboard/      Power BI file and screenshots
docs/           definitions, data notes, findings
data/raw/       cached API responses (git-ignored)
```

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

createdb shot_theory
psql -d shot_theory -f sql/01_schema.sql

# start small: two weeks of games
python src/ingest_nhl.py --start 2025-10-07 --end 2025-10-20
```

## Data
Source: the NHL's public web API (`api-web.nhle.com`). It is unofficial and undocumented, so it can change without notice.
Raw responses are cached in `data/raw/` so re-runs are fast and the analysis is reproducible.

**Scope for v1:** regular-season skater stats, team game stats, goals, penalties.
**Not yet loaded:** goalie game stats, shift/line data, expected goals.

## Roadmap
- [x] Schema design
- [x] Ingestion script (needs a first live run)
- [ ] Load one full season, validate against official standings
- [ ] SQL analysis for the six questions
- [ ] Power BI dashboard (League, Team, Player, Game)
- [ ] Written case study
- [ ] Advanced: shot quality / expected goals using goal and shot coordinates

## Validation checks (run after every load)
- Games per team is about 82 for a full regular season
- Team W/L/OTL and points match the NHL standings
- Sum of player goals equals team goals (excluding shootout and empty-net edge cases)
