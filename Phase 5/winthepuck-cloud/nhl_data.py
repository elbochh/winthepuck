"""Filling the database with real NHL data, and keeping it up to date.

Two things happen in this file:

  build_from_files()   runs once, the very first time the site starts. It reads
                       the JSON files in data/ (exported from our Phase 2 model)
                       and creates the teams, the finished games with the real
                       probability the model gave them, the playoff replay and
                       the starting accounts.

  apply_refresh()      runs every time the daily prediction job sends new data.
                       It updates the league table, adds the new predictions for
                       upcoming games, fills in scores for games that have just
                       been played and scores everybody's picks.

Nothing in here invents a number. Every probability comes from the model and
every result comes from the NHL.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

import config
import database
import scoring

# The clubs' primary colours, used for the logo squares and the probability
# bars. These are the only hand-typed values on the whole site.
TEAM_COLORS = {
    "ANA": "#F47A38", "ARI": "#8C2633", "BOS": "#FFB81C", "BUF": "#003087",
    "CGY": "#D2001C", "CAR": "#CE1126", "CHI": "#CF0A2C", "COL": "#6F263D",
    "CBJ": "#002654", "DAL": "#006847", "DET": "#CE1126", "EDM": "#FF4C00",
    "FLA": "#C8102E", "LAK": "#111111", "MIN": "#154734", "MTL": "#AF1E2D",
    "NSH": "#FFB81C", "NJD": "#CE1126", "NYI": "#00539B", "NYR": "#0038A8",
    "OTT": "#DA1A32", "PHI": "#F74902", "PIT": "#FCB514", "SEA": "#99D9D9",
    "SJS": "#006D75", "STL": "#002F87", "TBL": "#002868", "TOR": "#00205B",
    "UTA": "#71AFE5", "VAN": "#00843D", "VGK": "#B4975A", "WPG": "#041E42",
    "WSH": "#C8102E",
}
FALLBACK_COLOR = "#64748b"

# The picking strategies that fill the leaderboard on day one. Every one of
# them is a real back-test: the pick is worked out from the real game, and the
# points come from the real result. Nothing is typed in by hand.
STRATEGIES = [
    ("ModelFollower", 205, "Always backs the WinThePuck model"),
    ("HomeIceFan",     30, "Always backs the home team"),
    ("RoadWarrior",   115, "Always backs the visiting team"),
    ("FormChaser",  285, "Backs whichever team is on the better run"),
    ("Contrarian",    350, "Always bets against the model"),
]


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def read_seed(name: str) -> dict | None:
    path = config.SEED_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================
# TEAMS
# ===========================================================

def team_ids(connection: sqlite3.Connection) -> dict[str, int]:
    return {row["abbr"]: row["id"]
            for row in connection.execute("SELECT abbr, id FROM teams")}


def upsert_teams(connection: sqlite3.Connection, teams: list[dict]) -> dict[str, int]:
    """Add or update the 32 clubs and their season numbers."""
    for team in teams:
        stats = team.get("stats") or {}
        values = (
            team["abbr"], team.get("city", ""), team.get("name", team["abbr"]),
            TEAM_COLORS.get(team["abbr"], FALLBACK_COLOR), team.get("logo", ""),
            team.get("record", "0-0-0"), int(team.get("points", 0)),
            float(team.get("pointsPct", 0)), int(team.get("gamesPlayed", 0)),
            team.get("streak", ""), team.get("elo"),
            stats.get("goalsFor"), stats.get("goalsAgainst"),
            stats.get("powerPlay"), stats.get("penaltyKill"),
            stats.get("shotsPerGame"), stats.get("shotsAgainst"),
            stats.get("faceoffWin"), team.get("statsSeason"),
            ",".join(team.get("form") or []),
        )
        connection.execute(
            """INSERT INTO teams
                 (abbr, city, name, color, logo, record, points, points_pct,
                  games_played, streak, elo, goals_for, goals_against,
                  power_play, penalty_kill, shots_per_game, shots_against,
                  faceoff_win, stats_season, recent_form)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (abbr) DO UPDATE SET
                 city = excluded.city, name = excluded.name,
                 logo = excluded.logo, record = excluded.record,
                 points = excluded.points, points_pct = excluded.points_pct,
                 games_played = excluded.games_played, streak = excluded.streak,
                 elo = excluded.elo,
                 goals_for = excluded.goals_for,
                 goals_against = excluded.goals_against,
                 power_play = excluded.power_play,
                 penalty_kill = excluded.penalty_kill,
                 shots_per_game = excluded.shots_per_game,
                 shots_against = excluded.shots_against,
                 faceoff_win = excluded.faceoff_win,
                 stats_season = excluded.stats_season,
                 recent_form = excluded.recent_form""",
            values,
        )
    connection.commit()
    return team_ids(connection)


def ensure_team(connection: sqlite3.Connection, abbr: str,
                known: dict[str, int]) -> int | None:
    """Make a bare team row for a club we have games for but no table entry."""
    if abbr in known:
        return known[abbr]
    if not abbr:
        return None
    connection.execute(
        """INSERT INTO teams (abbr, city, name, color)
           VALUES (?, '', ?, ?) ON CONFLICT (abbr) DO NOTHING""",
        (abbr, abbr, TEAM_COLORS.get(abbr, FALLBACK_COLOR)),
    )
    row = connection.execute("SELECT id FROM teams WHERE abbr = ?", (abbr,)).fetchone()
    if row:
        known[abbr] = row["id"]
        return row["id"]
    return None


# ===========================================================
# GAMES
# ===========================================================

def upsert_upcoming(connection: sqlite3.Connection, games: list[dict],
                    known: dict[str, int], season: int) -> int:
    """Save the model's prediction for each game that has not been played."""
    saved = 0
    for game in games:
        home = ensure_team(connection, game["home"], known)
        away = ensure_team(connection, game["away"], known)
        if home is None or away is None:
            continue
        connection.execute(
            """INSERT INTO games
                 (nhl_game_id, season, game_date, start_time_utc, venue,
                  home_team_id, away_team_id, home_win_prob, confidence,
                  home_odds, away_odds, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming')
               ON CONFLICT (nhl_game_id) DO UPDATE SET
                 game_date = excluded.game_date,
                 start_time_utc = excluded.start_time_utc,
                 venue = excluded.venue,
                 home_win_prob = excluded.home_win_prob,
                 confidence = excluded.confidence,
                 home_odds = excluded.home_odds,
                 away_odds = excluded.away_odds
               WHERE games.status = 'upcoming'""",
            (game["gameId"], season, game["gameDate"],
             game.get("startTimeUtc", ""), game.get("venue", ""),
             home, away, game["homeWinProb"], game["confidence"],
             game["homeOdds"], game["awayOdds"]),
        )
        saved += 1
    connection.commit()
    return saved


def apply_results(connection: sqlite3.Connection, finished: list[dict],
                  known: dict[str, int]) -> int:
    """Fill in the score of any game that has now been played."""
    updated = 0
    for game in finished:
        winner = known.get(game["winner"])
        if winner is None:
            continue
        cursor = connection.execute(
            """UPDATE games
               SET status = 'final', home_score = ?, away_score = ?,
                   winner_team_id = ?
               WHERE nhl_game_id = ? AND status != 'final'""",
            (int(game["homeScore"]), int(game["awayScore"]), winner,
             game["gameId"]),
        )
        updated += cursor.rowcount
    connection.commit()
    return updated


def load_season_history(connection: sqlite3.Connection, history: dict,
                        known: dict[str, int]) -> int:
    """
    Load a whole finished season: real games, real scores, and the probability
    the model gave each one *before* it was played.

    These come from the walk-forward test in Phase 2, where the model was only
    ever allowed to learn from games that had already happened. That is why we
    can put them on the site as an honest track record.
    """
    season = history["season"]
    added = 0
    for game in history["games"]:
        home = ensure_team(connection, game["home"], known)
        away = ensure_team(connection, game["away"], known)
        if home is None or away is None:
            continue
        winner = home if game["winner"] == game["home"] else away
        connection.execute(
            """INSERT INTO games
                 (nhl_game_id, season, game_date, home_team_id, away_team_id,
                  home_win_prob, confidence, home_odds, away_odds, status,
                  home_score, away_score, winner_team_id, is_playoff)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'final', ?, ?, ?, ?)
               ON CONFLICT (nhl_game_id) DO NOTHING""",
            (game["gameId"], season, game["gameDate"], home, away,
             game["homeWinProb"], game["confidence"],
             american_odds(game["homeWinProb"] / 100),
             american_odds(1 - game["homeWinProb"] / 100),
             game["homeScore"], game["awayScore"], winner,
             1 if game["playoff"] else 0),
        )
        added += 1
    connection.commit()
    return added


def american_odds(probability: float) -> int:
    """The betting odds that match a probability exactly, with no house edge."""
    probability = min(max(probability, 0.02), 0.98)
    if probability >= 0.5:
        return int(round(-100 * probability / (1 - probability)))
    return int(round(100 * (1 - probability) / probability))


# ===========================================================
# MODEL SCORECARD AND THE PLAYOFF REPLAY
# ===========================================================

def load_model_report(connection: sqlite3.Connection, report: dict) -> None:
    connection.execute("DELETE FROM model_metrics")
    for row in report.get("perModel", []):
        connection.execute(
            """INSERT INTO model_metrics
                 (rank, model, accuracy, log_loss, correct_picks, games, best_streak)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (row["rank"], row["model"], row["accuracy"], row["logLoss"],
             row["correctPicks"], row["games"], row["bestStreak"]),
        )
    for key in ("testedGames", "testedSeasons", "overallAccuracy",
                "confidentAccuracy", "confidentGames"):
        if key in report:
            database.set_meta(connection, f"model_{key}", report[key])
    connection.commit()


def load_replay(connection: sqlite3.Connection, replay: dict,
                known: dict[str, int]) -> None:
    """Store one real playoff game so the home page can play it back."""
    home = ensure_team(connection, replay["home"], known)
    away = ensure_team(connection, replay["away"], known)
    if home is None or away is None:
        return

    connection.execute("DELETE FROM replay_events")
    connection.execute("DELETE FROM replay_game")
    connection.execute(
        """INSERT INTO replay_game
             (nhl_game_id, played_on, title, home_team_id, away_team_id,
              final_home, final_away, pregame_home_prob, current_step)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 2)""",
        (replay["gameId"], replay["date"], replay.get("label", "Playoff replay"),
         home, away, replay["finalHome"], replay["finalAway"],
         replay["pregameHomeProb"]),
    )
    for step, event in enumerate(replay["timeline"]):
        connection.execute(
            """INSERT INTO replay_events
                 (step, minute, period, clock, label, team, home_prob,
                  home_score, away_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (step, event["minute"], event["period"], event["clock"],
             event["label"], event.get("team", "neutral"), event["homeProb"],
             event["homeScore"], event["awayScore"]),
        )
    connection.commit()


# ===========================================================
# ACCOUNTS AND THE STARTING LEADERBOARD
# ===========================================================

def create_account(connection: sqlite3.Connection, username: str, password: str,
                   hue: int, kind: str, tagline: str) -> int:
    connection.execute(
        """INSERT INTO users (username, password_hash, hue, kind, tagline, joined_on)
           VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (username) DO NOTHING""",
        (username, generate_password_hash(password), hue, kind, tagline, today()),
    )
    return connection.execute(
        "SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]


def better_run(form: dict[str, list[int]], home: str, away: str) -> str:
    """Which of two teams has won more of its recent games (home wins a tie)."""
    home_run = sum(form.get(home, [])[-5:])
    away_run = sum(form.get(away, [])[-5:])
    return away if away_run > home_run else home


def seed_strategy_picks(connection: sqlite3.Connection, history: dict,
                        known: dict[str, int]) -> int:
    """
    Give each strategy account its picks for the real playoff games.

    Every pick follows the strategy's own rule, and is then scored against the
    real result, so the leaderboard is a genuine comparison of five ways of
    picking a hockey game.
    """
    accounts = {name: create_account(connection, name, _bot_password(name),
                                     hue, "strategy", tagline)
                for name, hue, tagline in STRATEGIES}

    playoff_games = [g for g in history["games"] if g["playoff"]]
    form: dict[str, list[int]] = {}
    added = 0

    for game in playoff_games:
        row = connection.execute(
            "SELECT id, home_team_id, away_team_id FROM games WHERE nhl_game_id = ?",
            (game["gameId"],)).fetchone()
        if row is None:
            continue

        model_pick = game["pick"]
        other = game["away"] if model_pick == game["home"] else game["home"]
        choices = {
            "ModelFollower": model_pick,
            "HomeIceFan": game["home"],
            "RoadWarrior": game["away"],
            "FormChaser": better_run(form, game["home"], game["away"]),
            "Contrarian": other,
        }
        for name, picked_abbr in choices.items():
            team_id = known.get(picked_abbr)
            if team_id is None:
                continue
            connection.execute(
                """INSERT INTO predictions (user_id, game_id, picked_team_id, made_on)
                   VALUES (?, ?, ?, ?) ON CONFLICT (user_id, game_id) DO NOTHING""",
                (accounts[name], row["id"], team_id, game["gameDate"]),
            )
            added += 1

        # remember who won, so "the better run" means something next time
        for team, won in ((game["home"], game["winner"] == game["home"]),
                          (game["away"], game["winner"] == game["away"])):
            form.setdefault(team, []).append(1 if won else 0)

    connection.commit()
    scoring.settle_predictions(connection)
    return added


def _bot_password(name: str) -> str:
    """Strategy accounts are not meant to be signed into, so give them a
    long random password nobody knows."""
    import secrets
    return f"{name}-{secrets.token_hex(24)}"


def seed_demo_account(connection: sqlite3.Connection) -> int:
    """One ordinary account so the members-only features can be tried out."""
    return create_account(connection, config.DEMO_USERNAME, config.DEMO_PASSWORD,
                          200, "member", "Demo account for marking")


# ===========================================================
# THE TWO ENTRY POINTS
# ===========================================================

def apply_refresh(payload: dict) -> dict:
    """Take a delivery from the daily prediction job and save all of it."""
    connection = database.get_connection()
    known = upsert_teams(connection, payload.get("teams", []))
    season = int(payload.get("season", 0))

    predicted = upsert_upcoming(connection, payload.get("upcoming", []), known, season)
    scored = apply_results(connection, payload.get("finished", []), known)
    if payload.get("modelReport"):
        load_model_report(connection, payload["modelReport"])

    # any game we predicted that has now been played needs its pick scored
    settled = scoring.settle_predictions(connection)

    database.set_meta(connection, "last_refresh", payload.get("generatedAt", ""))
    database.set_meta(connection, "current_season", season)
    database.set_meta(connection, "model_trained_to", payload.get("modelTrainedTo", ""))
    connection.commit()

    return {"teams": len(payload.get("teams", [])), "predictions": predicted,
            "results": scored, "picksScored": settled}


def build_from_files() -> dict:
    """Create the database and fill it from the exported model files."""
    database.build_tables()
    connection = database.get_connection()

    summary = {}
    first_refresh = read_seed("initial_refresh.json")
    known: dict[str, int] = {}
    if first_refresh:
        known = upsert_teams(connection, first_refresh.get("teams", []))
        season = int(first_refresh.get("season", 0))
        summary["upcoming"] = upsert_upcoming(
            connection, first_refresh.get("upcoming", []), known, season)
        database.set_meta(connection, "last_refresh",
                          first_refresh.get("generatedAt", ""))
        database.set_meta(connection, "current_season", season)
        database.set_meta(connection, "model_trained_to",
                          first_refresh.get("modelTrainedTo", ""))
    else:
        known = team_ids(connection)

    history = read_seed("season_history.json")
    if history:
        summary["history"] = load_season_history(connection, history, known)
        database.set_meta(connection, "history_label", history["label"])
        for key, value in history["summary"].items():
            database.set_meta(connection, f"history_{key}", value)

    report = read_seed("model_report.json")
    if report:
        load_model_report(connection, report)

    replay = read_seed("live_replay.json")
    if replay:
        load_replay(connection, replay, known)

    seed_demo_account(connection)
    if history:
        summary["strategyPicks"] = seed_strategy_picks(connection, history, known)

    database.set_meta(connection, "built_on", today())
    connection.commit()
    return summary
