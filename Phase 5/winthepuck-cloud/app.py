"""
WinThePuck - Flask web application
Phase 5: Cloud Deployment

Every page of the website lives in this file. A page reads what it needs out
of the SQLite database and hands it to a template in the templates folder.

What changed from Phase 4:
  * none of the hockey data is typed in any more. The teams, the games, the
    scores and the win probabilities all come from the NHL's public API and
    from the model we trained in Phase 2.
  * the database is created and filled automatically the first time the site
    starts, which is what lets it run in the cloud without anybody logging in
    to a server.
  * a protected /api/admin/refresh route lets the daily prediction job send in
    new predictions.

To run it on a laptop:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone
from math import ceil

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
import database
import nhl_data
import scoring

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Keep the login cookie away from JavaScript and off other people's websites.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=config.ON_AZURE,   # https only once we are deployed
    JSON_SORT_KEYS=False,
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)

app.teardown_appcontext(database.close_connection)

# The six numbers compared on the matchup page:
# column, label on screen, the value that fills the bar, unit, higher is better
STAT_ROWS = [
    ("goals_for",      "Goals for / game",     5.0,   "",  True),
    ("goals_against",  "Goals against / game", 5.0,   "",  False),
    ("power_play",     "Power play",           35.0,  "%", True),
    ("penalty_kill",   "Penalty kill",         100.0, "%", True),
    ("shots_per_game", "Shots / game",         40.0,  "",  True),
    ("faceoff_win",    "Faceoff win",          65.0,  "%", True),
]


# ===========================================================
# STARTING UP
# ===========================================================

def ensure_database() -> None:
    """
    Build and fill the database the first time the website is opened.

    On Azure gunicorn starts two copies of the app at the same time, so both
    could try to build the database at once and tread on each other. The lock
    file below means only the first one builds it; the other simply waits.
    """
    if database.tables_exist():
        return

    lock = config.DATA_DIR / "build.lock"
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # somebody else got here first - give them up to a minute to finish
        for _ in range(60):
            if database.tables_exist():
                return
            time.sleep(1)
        app.logger.warning("waited a minute for the database and gave up")
        return

    try:
        app.logger.info("no database yet - building it from the exported model files")
        summary = nhl_data.build_from_files()
        app.logger.info("database ready: %s", summary)
    finally:
        os.close(handle)
        lock.unlink(missing_ok=True)


with app.app_context():
    ensure_database()


# ===========================================================
# SMALL HELPERS
# ===========================================================

def logged_in() -> bool:
    return session.get("user_id") is not None


def csrf_token() -> str:
    """
    A one-per-visitor secret that every form has to send back.

    It stops another website from making your browser post something here
    without you knowing (a cross-site request forgery).
    """
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.before_request
def check_csrf() -> None:
    if request.method != "POST" or request.path.startswith("/api/"):
        return
    sent = request.form.get("csrf_token", "")
    if not sent or not secrets.compare_digest(sent, session.get("csrf_token", "")):
        abort(400, "That form was out of date. Please try again.")


def tidy(value):
    """Show 24 instead of 24.0, but leave a real decimal like 3.3 alone."""
    if value is None:
        return "-"
    if float(value) == int(value):
        return int(value)
    return round(float(value), 2)


def with_sign(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


def build_team(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"], "abbr": row["abbr"], "city": row["city"],
        "name": row["name"], "full_name": f"{row['city']} {row['name']}".strip(),
        "color": row["color"], "logo": row["logo"], "record": row["record"],
        "points": row["points"], "points_pct": row["points_pct"],
        "games_played": row["games_played"], "streak": row["streak"],
        "elo": round(row["elo"]) if row["elo"] is not None else None,
        "goals_for": row["goals_for"], "goals_against": row["goals_against"],
        "power_play": row["power_play"], "penalty_kill": row["penalty_kill"],
        "shots_per_game": row["shots_per_game"], "shots_against": row["shots_against"],
        "faceoff_win": row["faceoff_win"],
        "form": [r for r in (row["recent_form"] or "").split(",") if r],
    }


GAME_SELECT = """
    SELECT games.*,
           home.id AS h_id, home.abbr AS h_abbr, home.city AS h_city,
           home.name AS h_name, home.color AS h_color, home.logo AS h_logo,
           home.record AS h_record, home.recent_form AS h_form,
           home.points AS h_points, home.elo AS h_elo,
           home.goals_for AS h_gf, home.goals_against AS h_ga,
           home.power_play AS h_pp, home.penalty_kill AS h_pk,
           home.shots_per_game AS h_shots, home.faceoff_win AS h_fo,
           home.games_played AS h_gp, home.streak AS h_streak,
           home.points_pct AS h_pct, home.shots_against AS h_sa,
           away.id AS a_id, away.abbr AS a_abbr, away.city AS a_city,
           away.name AS a_name, away.color AS a_color, away.logo AS a_logo,
           away.record AS a_record, away.recent_form AS a_form,
           away.points AS a_points, away.elo AS a_elo,
           away.goals_for AS a_gf, away.goals_against AS a_ga,
           away.power_play AS a_pp, away.penalty_kill AS a_pk,
           away.shots_per_game AS a_shots, away.faceoff_win AS a_fo,
           away.games_played AS a_gp, away.streak AS a_streak,
           away.points_pct AS a_pct, away.shots_against AS a_sa
    FROM games
    JOIN teams AS home ON home.id = games.home_team_id
    JOIN teams AS away ON away.id = games.away_team_id
"""


def side_team(row, prefix: str) -> dict:
    """Pull one team out of a joined game row."""
    return {
        "id": row[f"{prefix}_id"], "abbr": row[f"{prefix}_abbr"],
        "city": row[f"{prefix}_city"], "name": row[f"{prefix}_name"],
        "full_name": f"{row[f'{prefix}_city']} {row[f'{prefix}_name']}".strip(),
        "color": row[f"{prefix}_color"], "logo": row[f"{prefix}_logo"],
        "record": row[f"{prefix}_record"], "points": row[f"{prefix}_points"],
        "points_pct": row[f"{prefix}_pct"], "games_played": row[f"{prefix}_gp"],
        "streak": row[f"{prefix}_streak"],
        "elo": round(row[f"{prefix}_elo"]) if row[f"{prefix}_elo"] is not None else None,
        "goals_for": row[f"{prefix}_gf"], "goals_against": row[f"{prefix}_ga"],
        "power_play": row[f"{prefix}_pp"], "penalty_kill": row[f"{prefix}_pk"],
        "shots_per_game": row[f"{prefix}_shots"], "shots_against": row[f"{prefix}_sa"],
        "faceoff_win": row[f"{prefix}_fo"],
        "form": [r for r in (row[f"{prefix}_form"] or "").split(",") if r],
    }


def build_game(row) -> dict | None:
    if row is None:
        return None
    home, away = side_team(row, "h"), side_team(row, "a")
    home_prob = round(row["home_win_prob"], 1)
    away_prob = round(100 - home_prob, 1)

    favourite, edge = (home, home_prob) if home_prob >= 50 else (away, away_prob)
    game = {
        "id": row["id"], "nhl_game_id": row["nhl_game_id"],
        "date": row["game_date"], "start_time_utc": row["start_time_utc"],
        "venue": row["venue"], "status": row["status"],
        "home": home, "away": away,
        "home_win_prob": home_prob, "away_win_prob": away_prob,
        "confidence": round(row["confidence"], 1),
        "home_odds": with_sign(row["home_odds"]),
        "away_odds": with_sign(row["away_odds"]),
        "favourite": favourite, "edge": edge,
        "home_score": row["home_score"], "away_score": row["away_score"],
        "winner_team_id": row["winner_team_id"],
        "is_playoff": bool(row["is_playoff"]),
        "label": f"{away['abbr']} @ {home['abbr']}",
        "time": friendly_time(row["start_time_utc"], row["game_date"]),
    }
    if row["status"] == "final" and row["winner_team_id"] is not None:
        game["winner"] = home if row["winner_team_id"] == home["id"] else away
        game["model_was_right"] = row["winner_team_id"] == favourite["id"]
    return game


def friendly_time(start_utc: str, game_date: str) -> str:
    """A short date to print next to a game, e.g. 'Tue 29 Sep, 23:00 UTC'."""
    if start_utc:
        try:
            moment = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
            return moment.strftime("%a %d %b, %H:%M UTC")
        except ValueError:
            pass
    return game_date


def games_where(clause: str, values: tuple = (), limit: int | None = None) -> list[dict]:
    sql = GAME_SELECT + clause
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [build_game(row) for row in database.query_all(sql, values)]


def get_game(game_id: int) -> dict | None:
    return build_game(database.query_one(GAME_SELECT + " WHERE games.id = ?", (game_id,)))


def upcoming_games(limit: int | None = None) -> list[dict]:
    return games_where(
        " WHERE games.status = 'upcoming' ORDER BY games.game_date, games.nhl_game_id",
        limit=limit)


# ===========================================================
# THE PLAYOFF REPLAY ON THE HOME PAGE
# ===========================================================

def replay_snapshot(advance: bool) -> dict | None:
    """
    Where the replayed playoff game has got to.

    The database remembers how many events have been shown. Asking for the
    next one is what makes the chart move while you watch it.
    """
    game = database.query_one("SELECT * FROM replay_game LIMIT 1")
    if game is None:
        return None

    events = database.query_all("SELECT * FROM replay_events ORDER BY step")
    if len(events) < 3:
        return None

    step = game["current_step"]
    if advance:
        step += 1
        if step > len(events) - 1:      # at the final horn, start again
            step = 2
        database.run_command(
            "UPDATE replay_game SET current_step = ? WHERE id = ?", (step, game["id"]))

    current, previous = events[step], events[step - 1]
    home = build_team(database.query_one(
        "SELECT * FROM teams WHERE id = ?", (game["home_team_id"],)))
    away = build_team(database.query_one(
        "SELECT * FROM teams WHERE id = ?", (game["away_team_id"],)))

    return {
        "title": game["title"],
        "played_on": game["played_on"],
        "nhl_game_id": game["nhl_game_id"],
        "home_team": home, "away_team": away,
        "home_abbr": home["abbr"], "away_abbr": away["abbr"],
        "home_prob": round(current["home_prob"], 1),
        "away_prob": round(100 - current["home_prob"], 1),
        "home_score": current["home_score"], "away_score": current["away_score"],
        "minute": current["minute"], "period": current["period"],
        "clock": current["clock"], "event_label": current["label"],
        "change": round(current["home_prob"] - previous["home_prob"], 1),
        "events": [
            {"minute": e["minute"], "label": e["label"],
             "home_prob": round(e["home_prob"], 1), "period": e["period"]}
            for e in events[: step + 1]
        ],
        "total_events": len(events),
        "final_home": game["final_home"], "final_away": game["final_away"],
    }


# ===========================================================
# THE LEADERBOARD
# ===========================================================

def get_leaderboard() -> list[dict]:
    """Add up everybody's finished picks, best first."""
    connection = database.get_connection()
    scoring.settle_predictions(connection)

    rows = database.query_all(
        """SELECT users.id, users.username, users.hue, users.kind, users.tagline,
                  COUNT(predictions.id) AS total_picks,
                  SUM(predictions.is_correct) AS correct_picks,
                  SUM(predictions.points) AS points
           FROM users
           JOIN predictions ON predictions.user_id = users.id
           WHERE predictions.is_correct IS NOT NULL
           GROUP BY users.id
           ORDER BY points DESC, correct_picks DESC"""
    )

    # One query for every settled pick, newest first, so we can work out each
    # member's winning streak without asking the database once per member.
    streaks: dict[int, list[int]] = {}
    for pick in database.query_all(
        """SELECT user_id, is_correct FROM predictions
           WHERE is_correct IS NOT NULL ORDER BY game_id DESC, id DESC"""
    ):
        streaks.setdefault(pick["user_id"], []).append(pick["is_correct"])

    board = []
    for rank, row in enumerate(rows, start=1):
        board.append({
            "rank": rank, "user_id": row["id"], "username": row["username"],
            "hue": row["hue"], "kind": row["kind"], "tagline": row["tagline"],
            "initials": row["username"][:2].upper(),
            "accuracy": round(row["correct_picks"] / row["total_picks"] * 100, 1),
            "streak": scoring.count_streak(streaks.get(row["id"], [])),
            "points": row["points"], "total_picks": row["total_picks"],
            "correct_picks": row["correct_picks"],
        })
    return board


# ===========================================================
# COMMENTS AND PICKS
# ===========================================================

def get_comments(game_id: int) -> list[dict]:
    """Every message on one game, newest first, with its like count."""
    user_id = session.get("user_id") or -1
    rows = database.query_all(
        """SELECT comments.*, users.username, users.hue,
                  (SELECT COUNT(*) FROM comment_likes
                    WHERE comment_likes.comment_id = comments.id) AS likes,
                  EXISTS (SELECT 1 FROM comment_likes
                           WHERE comment_likes.comment_id = comments.id
                             AND comment_likes.user_id = ?) AS liked_by_me
           FROM comments
           JOIN users ON users.id = comments.user_id
           WHERE comments.game_id = ?
           ORDER BY comments.id DESC""",
        (user_id, game_id),
    )
    return [
        {"id": r["id"], "username": r["username"], "hue": r["hue"],
         "initials": r["username"][:2].upper(), "body": r["body"],
         "pick": r["pick"], "likes": r["likes"],
         "liked_by_me": bool(r["liked_by_me"]), "posted_on": r["posted_on"]}
        for r in rows
    ]


def my_pick(game_id: int) -> int | None:
    if not logged_in():
        return None
    row = database.query_one(
        "SELECT picked_team_id FROM predictions WHERE user_id = ? AND game_id = ?",
        (session["user_id"], game_id))
    return row["picked_team_id"] if row else None


@app.context_processor
def shared_values() -> dict:
    """Values every template can use without us passing them in each time."""
    return {
        "current_user": session.get("username"),
        "logged_in": logged_in(),
        "csrf_token": csrf_token(),
        "this_year": datetime.now().year,
        "last_refresh": database.get_meta("last_refresh"),
    }


# ===========================================================
# PAGES
# ===========================================================

@app.route("/")
def home():
    """The front page: the replay, the next games and the top of the table."""
    history_label = database.get_meta("history_label", "last season")
    return render_template(
        "index.html",
        replay=replay_snapshot(False),
        games=upcoming_games(limit=3),
        top_members=get_leaderboard()[:3],
        stats={
            "accuracy": database.get_meta("model_overallAccuracy", "0"),
            "confident_accuracy": database.get_meta("model_confidentAccuracy", "0"),
            "tested_games": database.get_meta("model_testedGames", "0"),
            "season_label": history_label,
            "season_accuracy": database.get_meta("history_accuracy", "0"),
            "season_games": database.get_meta("history_games", "0"),
            "upcoming": database.query_value(
                "SELECT COUNT(*) FROM games WHERE status = 'upcoming'", default=0),
            "finished": database.query_value(
                "SELECT COUNT(*) FROM games WHERE status = 'final'", default=0),
        },
    )


@app.route("/games")
def games_page():
    """Every upcoming game with the model's prediction, odds and confidence."""
    games = upcoming_games()
    for game in games:
        game["my_pick"] = my_pick(game["id"])
    return render_template("games.html", games=games,
                           season_starts=games[0]["date"] if games else None)


@app.route("/matchups")
@app.route("/matchups/<int:game_id>")
def matchups_page(game_id: int | None = None):
    """Compare the two teams in a game, stat by stat."""
    games = upcoming_games()
    if not games:
        return render_template("matchups.html", games=[], game=None, stat_rows=[])

    game = games[0] if game_id is None else get_game(game_id)
    if game is None:
        abort(404)

    rows = []
    for column, label, biggest, unit, higher_is_better in STAT_ROWS:
        home_value, away_value = game["home"][column], game["away"][column]
        if home_value is None or away_value is None:
            continue
        home_wins = (home_value > away_value) if higher_is_better else (home_value < away_value)
        rows.append({
            "label": label, "unit": unit,
            "home_value": tidy(home_value), "away_value": tidy(away_value),
            "home_width": max(4, min(100, round(home_value / biggest * 100))),
            "away_width": max(4, min(100, round(away_value / biggest * 100))),
            "home_wins": home_wins,
        })

    return render_template("matchups.html", games=games, game=game, stat_rows=rows)


@app.route("/results")
def results_page():
    """
    Every game the model has already been graded on.

    This is the honest scoreboard: the probability shown was worked out before
    the game was played, and the tick or cross is the real result.
    """
    page = max(1, request.args.get("page", type=int, default=1))
    only = request.args.get("filter", "all")

    clause = " WHERE games.status = 'final'"
    if only == "correct":
        clause += " AND ((games.home_win_prob >= 50 AND games.winner_team_id = games.home_team_id)" \
                  " OR (games.home_win_prob < 50 AND games.winner_team_id = games.away_team_id))"
    elif only == "missed":
        clause += " AND ((games.home_win_prob >= 50 AND games.winner_team_id != games.home_team_id)" \
                  " OR (games.home_win_prob < 50 AND games.winner_team_id != games.away_team_id))"
    elif only == "playoffs":
        clause += " AND games.is_playoff = 1"

    total = database.query_value(
        "SELECT COUNT(*) FROM games" + clause.replace("games.", "games."), default=0)
    pages = max(1, ceil(total / config.RESULTS_PAGE_SIZE))
    page = min(page, pages)
    offset = (page - 1) * config.RESULTS_PAGE_SIZE

    games = games_where(
        clause + " ORDER BY games.game_date DESC, games.nhl_game_id DESC"
        f" LIMIT {config.RESULTS_PAGE_SIZE} OFFSET {offset}")

    graded = database.query_all(
        """SELECT model, accuracy, log_loss, correct_picks, games, best_streak, rank
           FROM model_metrics ORDER BY rank""")

    return render_template(
        "results.html", games=games, page=page, pages=pages, total=total,
        only=only, model_rows=graded,
        summary={
            "label": database.get_meta("history_label", ""),
            "accuracy": database.get_meta("history_accuracy", "0"),
            "games": database.get_meta("history_games", "0"),
            "confident_accuracy": database.get_meta("history_confidentAccuracy", "0"),
            "confident_games": database.get_meta("history_confidentGames", "0"),
            "tested_games": database.get_meta("model_testedGames", "0"),
            "tested_seasons": database.get_meta("model_testedSeasons", "0"),
            "overall_accuracy": database.get_meta("model_overallAccuracy", "0"),
        },
    )


@app.route("/leaderboard")
def leaderboard_page():
    board = get_leaderboard()
    my_row = next((m for m in board if m["user_id"] == session.get("user_id")), None)

    pending = 0
    if logged_in():
        pending = database.query_value(
            "SELECT COUNT(*) FROM predictions WHERE user_id = ? AND is_correct IS NULL",
            (session["user_id"],), default=0)

    return render_template("leaderboard.html", board=board, podium=board[:3],
                           my_row=my_row, pending=pending)


@app.route("/discussion")
@app.route("/discussion/<int:game_id>")
def discussion_page(game_id: int | None = None):
    """Read and post messages about a game."""
    games = upcoming_games(limit=30)
    if not games:
        games = games_where(
            " WHERE games.status = 'final' ORDER BY games.game_date DESC", limit=10)
    if not games:
        abort(404)

    game = games[0] if game_id is None else get_game(game_id)
    if game is None:
        abort(404)

    return render_template("discussion.html", games=games, game=game,
                           comments=get_comments(game["id"]))


# ===========================================================
# FORMS THAT SEND DATA BACK
# ===========================================================

@app.route("/discussion/<int:game_id>/post", methods=["POST"])
def post_comment(game_id: int):
    if not logged_in():
        flash("Please sign in before posting a message.", "error")
        return redirect(url_for("login"))
    if get_game(game_id) is None:
        abort(404)

    body = request.form.get("body", "").strip()
    pick = request.form.get("pick", "home")
    if pick not in ("home", "away"):
        pick = "home"

    if not body:
        flash("Your message was empty, so it was not posted.", "error")
    elif len(body) > 500:
        flash("Messages have to be shorter than 500 characters.", "error")
    else:
        database.run_command(
            """INSERT INTO comments (game_id, user_id, body, pick, posted_on)
               VALUES (?, ?, ?, ?, ?)""",
            (game_id, session["user_id"], body, pick, nhl_data.today()))
        flash("Your message was posted.", "success")

    return redirect(url_for("discussion_page", game_id=game_id))


@app.route("/comment/<int:comment_id>/like", methods=["POST"])
def like_comment(comment_id: int):
    if not logged_in():
        flash("Please sign in to like a message.", "error")
        return redirect(url_for("login"))

    comment = database.query_one("SELECT * FROM comments WHERE id = ?", (comment_id,))
    if comment is None:
        abort(404)

    user_id = session["user_id"]
    already = database.query_one(
        "SELECT 1 FROM comment_likes WHERE comment_id = ? AND user_id = ?",
        (comment_id, user_id))

    if already is None:
        database.run_command(
            "INSERT INTO comment_likes (comment_id, user_id) VALUES (?, ?)",
            (comment_id, user_id))
    else:
        database.run_command(
            "DELETE FROM comment_likes WHERE comment_id = ? AND user_id = ?",
            (comment_id, user_id))

    return redirect(url_for("discussion_page", game_id=comment["game_id"]))


@app.route("/predict/<int:game_id>", methods=["POST"])
def make_prediction(game_id: int):
    """Save the member's pick for an upcoming game."""
    if not logged_in():
        flash("Please sign in to save a pick.", "error")
        return redirect(url_for("login"))

    game = get_game(game_id)
    if game is None:
        abort(404)
    if game["status"] != "upcoming":
        flash("That game has already been played, so picks are closed.", "error")
        return redirect(url_for("games_page"))

    team_id = request.form.get("team_id", "")
    if not team_id.isdigit():
        flash("Please choose a team.", "error")
        return redirect(url_for("games_page"))

    team_id = int(team_id)
    if team_id not in (game["home"]["id"], game["away"]["id"]):
        flash("That team is not playing in this game.", "error")
        return redirect(url_for("games_page"))

    database.run_command(
        """INSERT INTO predictions (user_id, game_id, picked_team_id, made_on)
           VALUES (?, ?, ?, ?)
           ON CONFLICT (user_id, game_id)
           DO UPDATE SET picked_team_id = excluded.picked_team_id""",
        (session["user_id"], game_id, team_id, nhl_data.today()))

    picked = game["home"] if team_id == game["home"]["id"] else game["away"]
    flash(f"Pick saved: {picked['full_name']}.", "success")
    return redirect(url_for("games_page", _anchor=f"game-{game_id}"))


# ===========================================================
# MEMBER ACCOUNTS
# ===========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if len(username) < 3 or len(username) > 20:
            flash("Your username needs between 3 and 20 characters.", "error")
        elif not username.replace("_", "").isalnum():
            flash("Usernames can only use letters, numbers and underscores.", "error")
        elif len(password) < 6:
            flash("Your password needs at least 6 characters.", "error")
        elif password != confirm:
            flash("The two passwords do not match.", "error")
        elif database.query_one("SELECT 1 FROM users WHERE username = ?", (username,)):
            flash("That username is already taken.", "error")
        else:
            user_id = database.run_command(
                """INSERT INTO users (username, password_hash, hue, joined_on)
                   VALUES (?, ?, ?, ?)""",
                (username, generate_password_hash(password),
                 len(username) * 37 % 360, nhl_data.today()))
            session.clear()
            session["user_id"] = user_id
            session["username"] = username
            flash(f"Welcome to WinThePuck, {username}!", "success")
            return redirect(url_for("games_page"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.query_one(
            "SELECT * FROM users WHERE username = ? AND kind = 'member'", (username,))

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Wrong username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Signed in as {user['username']}.", "success")
            return redirect(url_for("home"))

    return render_template("login.html", demo_username=config.DEMO_USERNAME,
                           demo_password=config.DEMO_PASSWORD)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


# ===========================================================
# JSON API
# ===========================================================

@app.route("/api/games")
def api_games():
    return jsonify(upcoming_games())


@app.route("/api/live")
def api_live():
    """Move the playoff replay on by one event. main.js calls this on a timer."""
    snapshot = replay_snapshot(True)
    if snapshot is None:
        return jsonify({"error": "No replay loaded"}), 404
    return jsonify(snapshot)


@app.route("/api/leaderboard")
def api_leaderboard():
    return jsonify(get_leaderboard())


@app.route("/api/model")
def api_model():
    """The model's real scorecard from the Phase 2 walk-forward test."""
    return jsonify({
        "testedGames": database.get_meta("model_testedGames"),
        "overallAccuracy": database.get_meta("model_overallAccuracy"),
        "confidentAccuracy": database.get_meta("model_confidentAccuracy"),
        "trainedTo": database.get_meta("model_trained_to"),
        "lastRefresh": database.get_meta("last_refresh"),
        "models": [dict(row) for row in database.query_all(
            "SELECT * FROM model_metrics ORDER BY rank")],
    })


@app.route("/api/admin/refresh", methods=["POST"])
def api_refresh():
    """
    Where the daily prediction job delivers new predictions.

    It has to send the secret token we set in the Azure app settings, so nobody
    else can push made-up numbers into the site.
    """
    if not config.REFRESH_TOKEN:
        return jsonify({"error": "Refreshing is switched off on this server"}), 503

    header = request.headers.get("Authorization", "")
    supplied = header[7:] if header.startswith("Bearer ") else ""
    if not secrets.compare_digest(supplied, config.REFRESH_TOKEN):
        return jsonify({"error": "Wrong or missing token"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "teams" not in payload:
        return jsonify({"error": "That does not look like a refresh payload"}), 400

    summary = nhl_data.apply_refresh(payload)
    app.logger.info("refresh applied: %s", summary)
    return jsonify({"status": "ok", **summary})


@app.route("/healthz")
def healthz():
    """A tiny page Azure can call to check the site is alive."""
    try:
        teams = database.query_value("SELECT COUNT(*) FROM teams", default=0)
    except Exception as error:            # the database is missing or broken
        return jsonify({"status": "error", "detail": str(error)}), 500
    return jsonify({
        "status": "ok", "teams": teams,
        "games": database.query_value("SELECT COUNT(*) FROM games", default=0),
        "lastRefresh": database.get_meta("last_refresh"),
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


# ===========================================================
# ERROR PAGES
# ===========================================================

@app.errorhandler(400)
def bad_request(error):
    return render_template("404.html", code=400,
                           message=getattr(error, "description",
                                           "Something about that request was wrong.")), 400


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html", code=404,
                           message="We could not find that page."), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.exception("unhandled error")
    return render_template("404.html", code=500,
                           message="Something went wrong on our side."), 500


if __name__ == "__main__":
    app.run(debug=True)
