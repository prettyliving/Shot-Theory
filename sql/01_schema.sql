-- Shot Theory: PostgreSQL schema
-- Run: psql -d shot_theory -f sql/01_schema.sql

DROP TABLE IF EXISTS penalties, goals, team_game_stats, player_game_stats, games, players, teams CASCADE;

CREATE TABLE teams (
    team_id     INTEGER PRIMARY KEY,          -- NHL team id
    abbrev      TEXT NOT NULL UNIQUE,         -- e.g. BOS
    name        TEXT NOT NULL,                -- e.g. Boston Bruins
    conference  TEXT,
    division    TEXT
);

CREATE TABLE players (
    player_id   INTEGER PRIMARY KEY,          -- NHL player id
    first_name  TEXT,
    last_name   TEXT,
    position    TEXT                          -- C, L, R, D, G
);

CREATE TABLE games (
    game_id       BIGINT PRIMARY KEY,         -- NHL game id, e.g. 2025020001
    season        INTEGER NOT NULL,           -- e.g. 20252026
    game_type     SMALLINT NOT NULL,          -- 2 = regular season, 3 = playoffs
    game_date     DATE NOT NULL,
    home_team_id  INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id  INTEGER NOT NULL REFERENCES teams(team_id),
    home_score    SMALLINT,
    away_score    SMALLINT,
    ended_in      TEXT,                       -- REG, OT, SO
    CHECK (home_team_id <> away_team_id)
);
CREATE INDEX idx_games_date ON games (game_date);
CREATE INDEX idx_games_season ON games (season, game_type);

CREATE TABLE player_game_stats (
    game_id       BIGINT  NOT NULL REFERENCES games(game_id),
    player_id     INTEGER NOT NULL REFERENCES players(player_id),
    team_id       INTEGER NOT NULL REFERENCES teams(team_id),
    position      TEXT,
    goals         SMALLINT DEFAULT 0,
    assists       SMALLINT DEFAULT 0,
    points        SMALLINT DEFAULT 0,
    shots         SMALLINT DEFAULT 0,
    toi_seconds   INTEGER,
    pim           SMALLINT DEFAULT 0,
    plus_minus    SMALLINT,
    hits          SMALLINT,
    blocked_shots SMALLINT,
    pp_goals      SMALLINT DEFAULT 0,
    takeaways     SMALLINT,
    giveaways     SMALLINT,
    PRIMARY KEY (game_id, player_id)
);
CREATE INDEX idx_pgs_player ON player_game_stats (player_id);

CREATE TABLE team_game_stats (
    game_id        BIGINT  NOT NULL REFERENCES games(game_id),
    team_id        INTEGER NOT NULL REFERENCES teams(team_id),
    opponent_id    INTEGER NOT NULL REFERENCES teams(team_id),
    is_home        BOOLEAN NOT NULL,
    goals_for      SMALLINT,
    goals_against  SMALLINT,
    shots_for      SMALLINT,
    shots_against  SMALLINT,
    pp_goals       SMALLINT,
    pp_opportunities SMALLINT,
    pim            SMALLINT,
    result         TEXT,                      -- W, L, OTL (shootout loss counts as OTL)
    standings_pts  SMALLINT,                  -- 2, 1, or 0
    PRIMARY KEY (game_id, team_id)
);
CREATE INDEX idx_tgs_team ON team_game_stats (team_id);

CREATE TABLE goals (
    goal_id         SERIAL PRIMARY KEY,
    game_id         BIGINT  NOT NULL REFERENCES games(game_id),
    period          SMALLINT,
    time_in_period  TEXT,                     -- MM:SS elapsed
    team_id         INTEGER REFERENCES teams(team_id),
    scorer_id       INTEGER REFERENCES players(player_id),
    assist1_id      INTEGER REFERENCES players(player_id),
    assist2_id      INTEGER REFERENCES players(player_id),
    strength        TEXT,                     -- e.g. 5v5, 5v4, 4v5
    empty_net       BOOLEAN,
    shot_type       TEXT,
    x_coord         SMALLINT,
    y_coord         SMALLINT
);
CREATE INDEX idx_goals_game ON goals (game_id);

CREATE TABLE penalties (
    penalty_id      SERIAL PRIMARY KEY,
    game_id         BIGINT  NOT NULL REFERENCES games(game_id),
    period          SMALLINT,
    time_in_period  TEXT,
    team_id         INTEGER REFERENCES teams(team_id),
    player_id       INTEGER REFERENCES players(player_id),
    description     TEXT,
    severity        TEXT,                     -- MIN, MAJ, BEN, etc.
    minutes         SMALLINT
);
CREATE INDEX idx_penalties_game ON penalties (game_id);
