-- ===========================================================
-- WinThePuck - database tables
--
-- Everything in here is filled from real NHL data: the teams and their
-- records come from the NHL's public API, the win probabilities come from
-- the model we trained, and the finished games are real results.
-- ===========================================================

DROP TABLE IF EXISTS comment_likes;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS replay_events;
DROP TABLE IF EXISTS replay_game;
DROP TABLE IF EXISTS model_metrics;
DROP TABLE IF EXISTS games;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS site_meta;


-- ---- the 32 NHL clubs, with the season stats shown on the matchup page ----
CREATE TABLE teams (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    abbr           TEXT    NOT NULL UNIQUE,
    city           TEXT    NOT NULL,
    name           TEXT    NOT NULL,
    color          TEXT    NOT NULL,
    logo           TEXT    NOT NULL DEFAULT '',
    record         TEXT    NOT NULL DEFAULT '0-0-0',
    points         INTEGER NOT NULL DEFAULT 0,
    points_pct     REAL    NOT NULL DEFAULT 0,
    games_played   INTEGER NOT NULL DEFAULT 0,
    streak         TEXT    NOT NULL DEFAULT '',
    elo            REAL,
    goals_for      REAL,
    goals_against  REAL,
    power_play     REAL,
    penalty_kill   REAL,
    shots_per_game REAL,
    shots_against  REAL,
    faceoff_win    REAL,
    stats_season   INTEGER,
    recent_form    TEXT    NOT NULL DEFAULT ''   -- last 5 results, e.g. "W,W,L,W,O"
);


-- ---- games, and the probability the model gave each one ----
CREATE TABLE games (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nhl_game_id    INTEGER NOT NULL UNIQUE,      -- the id the NHL itself uses
    season         INTEGER NOT NULL,
    game_date      TEXT    NOT NULL,             -- YYYY-MM-DD
    start_time_utc TEXT    NOT NULL DEFAULT '',
    venue          TEXT    NOT NULL DEFAULT '',
    home_team_id   INTEGER NOT NULL,
    away_team_id   INTEGER NOT NULL,
    home_win_prob  REAL    NOT NULL,             -- 0 - 100, straight from the model
    confidence     REAL    NOT NULL,             -- 0 - 100
    home_odds      INTEGER NOT NULL,
    away_odds      INTEGER NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'upcoming',   -- upcoming | final
    home_score     INTEGER,
    away_score     INTEGER,
    winner_team_id INTEGER,
    is_playoff     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (home_team_id)   REFERENCES teams (id),
    FOREIGN KEY (away_team_id)   REFERENCES teams (id),
    FOREIGN KEY (winner_team_id) REFERENCES teams (id)
);

CREATE INDEX idx_games_status ON games (status, game_date);
CREATE INDEX idx_games_date   ON games (game_date);


-- ---- how well each model did in the walk-forward test ----
CREATE TABLE model_metrics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    rank          INTEGER NOT NULL,
    model         TEXT    NOT NULL,
    accuracy      REAL    NOT NULL,
    log_loss      REAL    NOT NULL,
    correct_picks INTEGER NOT NULL,
    games         INTEGER NOT NULL,
    best_streak   INTEGER NOT NULL
);


-- ---- one real playoff game, replayed event by event on the home page ----
CREATE TABLE replay_game (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nhl_game_id       INTEGER NOT NULL,
    played_on         TEXT    NOT NULL,
    title             TEXT    NOT NULL,
    home_team_id      INTEGER NOT NULL,
    away_team_id      INTEGER NOT NULL,
    final_home        INTEGER NOT NULL,
    final_away        INTEGER NOT NULL,
    pregame_home_prob REAL    NOT NULL,
    current_step      INTEGER NOT NULL DEFAULT 2,
    FOREIGN KEY (home_team_id) REFERENCES teams (id),
    FOREIGN KEY (away_team_id) REFERENCES teams (id)
);


-- ---- every event of that game, with the live model's win probability ----
CREATE TABLE replay_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    step       INTEGER NOT NULL,
    minute     REAL    NOT NULL,
    period     INTEGER NOT NULL,
    clock      TEXT    NOT NULL,
    label      TEXT    NOT NULL,
    team       TEXT    NOT NULL,
    home_prob  REAL    NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL
);


-- ---- website members ----
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    hue           INTEGER NOT NULL DEFAULT 200,      -- avatar colour
    kind          TEXT    NOT NULL DEFAULT 'member', -- member | strategy
    tagline       TEXT    NOT NULL DEFAULT '',
    joined_on     TEXT    NOT NULL
);


-- ---- every pick a member makes (this is what builds the leaderboard) ----
CREATE TABLE predictions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    game_id        INTEGER NOT NULL,
    picked_team_id INTEGER NOT NULL,
    is_correct     INTEGER,          -- 1 right, 0 wrong, NULL game not finished
    points         INTEGER NOT NULL DEFAULT 0,
    made_on        TEXT    NOT NULL,
    UNIQUE (user_id, game_id),
    FOREIGN KEY (user_id)        REFERENCES users (id),
    FOREIGN KEY (game_id)        REFERENCES games (id),
    FOREIGN KEY (picked_team_id) REFERENCES teams (id)
);

CREATE INDEX idx_predictions_user ON predictions (user_id, is_correct);


-- ---- discussion messages ----
CREATE TABLE comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    body       TEXT    NOT NULL,
    pick       TEXT    NOT NULL,      -- "home" or "away"
    posted_on  TEXT    NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX idx_comments_game ON comments (game_id, id);


-- ---- one row per like, so nobody can like the same message twice ----
CREATE TABLE comment_likes (
    comment_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    PRIMARY KEY (comment_id, user_id),
    FOREIGN KEY (comment_id) REFERENCES comments (id),
    FOREIGN KEY (user_id)    REFERENCES users (id)
);


-- ---- small notes about the site itself, such as when data last refreshed ----
CREATE TABLE site_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
