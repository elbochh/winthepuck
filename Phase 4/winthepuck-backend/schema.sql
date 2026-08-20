-- ===========================================================
-- WinThePuck - database tables
-- Phase 4: Back End Development
-- ===========================================================

-- Delete the old tables first so we can rebuild the database
-- any time we run seed_data.py.
DROP TABLE IF EXISTS comment_likes;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS live_events;
DROP TABLE IF EXISTS live_state;
DROP TABLE IF EXISTS games;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS users;


-- ---- NHL teams and their season stats ----
CREATE TABLE teams (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    abbr           TEXT    NOT NULL UNIQUE,
    city           TEXT    NOT NULL,
    name           TEXT    NOT NULL,
    color          TEXT    NOT NULL,
    record         TEXT    NOT NULL,
    goals_for      REAL    NOT NULL,
    goals_against  REAL    NOT NULL,
    power_play     REAL    NOT NULL,
    penalty_kill   REAL    NOT NULL,
    shots_per_game REAL    NOT NULL,
    faceoff_win    REAL    NOT NULL,
    recent_form    TEXT    NOT NULL   -- last 5 results, e.g. "W,W,L,W,O"
);


-- ---- games and the model prediction for each one ----
CREATE TABLE games (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    game_time      TEXT    NOT NULL,
    home_team_id   INTEGER NOT NULL,
    away_team_id   INTEGER NOT NULL,
    home_win_prob  INTEGER NOT NULL,   -- 0 - 100
    confidence     INTEGER NOT NULL,   -- 0 - 100
    home_odds      INTEGER NOT NULL,
    away_odds      INTEGER NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'upcoming',  -- upcoming | live | final
    home_score     INTEGER,
    away_score     INTEGER,
    winner_team_id INTEGER,
    FOREIGN KEY (home_team_id)   REFERENCES teams (id),
    FOREIGN KEY (away_team_id)   REFERENCES teams (id),
    FOREIGN KEY (winner_team_id) REFERENCES teams (id)
);


-- ---- play by play events for the live game ----
CREATE TABLE live_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    INTEGER NOT NULL,
    minute     INTEGER NOT NULL,
    label      TEXT    NOT NULL,
    home_prob  INTEGER NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games (id)
);


-- ---- how far the live game has played so far ----
CREATE TABLE live_state (
    game_id      INTEGER PRIMARY KEY,
    current_step INTEGER NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games (id)
);


-- ---- website members ----
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    hue           INTEGER NOT NULL DEFAULT 200,  -- avatar colour
    joined_on     TEXT    NOT NULL
);


-- ---- every pick a member makes (used to build the leaderboard) ----
CREATE TABLE predictions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    game_id        INTEGER NOT NULL,
    picked_team_id INTEGER NOT NULL,
    is_correct     INTEGER,             -- 1 = right, 0 = wrong, NULL = game not finished
    points         INTEGER NOT NULL DEFAULT 0,
    made_on        TEXT    NOT NULL,
    FOREIGN KEY (user_id)        REFERENCES users (id),
    FOREIGN KEY (game_id)        REFERENCES games (id),
    FOREIGN KEY (picked_team_id) REFERENCES teams (id)
);


-- ---- discussion messages ----
CREATE TABLE comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    body       TEXT    NOT NULL,
    pick       TEXT    NOT NULL,         -- "home" or "away"
    base_likes INTEGER NOT NULL DEFAULT 0,  -- likes the comment started with
    posted_on  TEXT    NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);


-- ---- one row per like, so a member can only like a comment once ----
CREATE TABLE comment_likes (
    comment_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    PRIMARY KEY (comment_id, user_id),
    FOREIGN KEY (comment_id) REFERENCES comments (id),
    FOREIGN KEY (user_id)    REFERENCES users (id)
);
