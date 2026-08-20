"""
WinThePuck - Flask web application
Phase 4: Back End Development

This file holds every page (route) of the website. Each route reads
the data it needs out of the SQLite database and then hands it to a
template in the templates folder.

To start the website:
    python seed_data.py     (only the first time, to build the database)
    python app.py
Then open http://127.0.0.1:5000 in a browser.
"""

from datetime import datetime

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import database
import scoring

app = Flask(__name__)

# The secret key lets Flask keep members logged in and show flash messages.
app.secret_key = "winthepuck-phase4-secret-key"

# The password every demo member uses, shown on the sign in page
# so the work is easy to test and mark.
DEMO_PASSWORD_HINT = "puck1234"

# The six stats compared on the matchup page.
# column name, label shown on screen, biggest value on the bar, unit
STAT_ROWS = [
    ("goals_for",      "Goals / game",  5,   ""),
    ("goals_against",  "Goals against", 5,   ""),
    ("power_play",     "Power play",    35,  "%"),
    ("penalty_kill",   "Penalty kill",  100, "%"),
    ("shots_per_game", "Shots / game",  40,  ""),
    ("faceoff_win",    "Faceoff win",   65,  "%"),
]


# ===========================================================
# HELPER FUNCTIONS
# ===========================================================

def format_odds(odds):
    """Betting odds are written with a + when they are positive."""
    if odds > 0:
        return "+" + str(odds)
    return str(odds)


def tidy_number(value):
    """
    SQLite gives every stat back as a decimal. Show 24 instead of 24.0
    but leave a real decimal like 3.3 alone.
    """
    if value == int(value):
        return int(value)
    return value


def build_team(row):
    """Turn a row from the teams table into a dictionary for the templates."""
    if row is None:
        return None

    return {
        "id": row["id"],
        "abbr": row["abbr"],
        "city": row["city"],
        "name": row["name"],
        "full_name": row["city"] + " " + row["name"],
        "color": row["color"],
        "record": row["record"],
        "goals_for": row["goals_for"],
        "goals_against": row["goals_against"],
        "power_play": row["power_play"],
        "penalty_kill": row["penalty_kill"],
        "shots_per_game": row["shots_per_game"],
        "faceoff_win": row["faceoff_win"],
        # "W,L,W" is easier to store, but a list is easier to loop over.
        "form": row["recent_form"].split(","),
    }


def get_team(team_id):
    """Find one team by its id."""
    return build_team(database.query_one("SELECT * FROM teams WHERE id = ?", (team_id,)))


def build_game(row):
    """Turn a row from the games table into a dictionary for the templates."""
    if row is None:
        return None

    home = get_team(row["home_team_id"])
    away = get_team(row["away_team_id"])
    home_prob = row["home_win_prob"]
    away_prob = 100 - home_prob

    # The favourite is whichever team the model gives the better chance to.
    if home_prob >= 50:
        favourite = home
        edge = home_prob
    else:
        favourite = away
        edge = away_prob

    return {
        "id": row["id"],
        "time": row["game_time"],
        "status": row["status"],
        "home": home,
        "away": away,
        "home_win_prob": home_prob,
        "away_win_prob": away_prob,
        "confidence": row["confidence"],
        "home_odds": format_odds(row["home_odds"]),
        "away_odds": format_odds(row["away_odds"]),
        "favourite": favourite,
        "edge": edge,
        "home_score": row["home_score"],
        "away_score": row["away_score"],
        "winner_team_id": row["winner_team_id"],
        "label": home["abbr"] + " v " + away["abbr"],
    }


def get_game(game_id):
    """Find one game by its id."""
    return build_game(database.query_one("SELECT * FROM games WHERE id = ?", (game_id,)))


def get_games_by_status(status):
    """Get every game that is upcoming, live or final."""
    rows = database.query_all(
        "SELECT * FROM games WHERE status = ? ORDER BY id", (status,)
    )

    games = []
    for row in rows:
        games.append(build_game(row))
    return games


def get_live_game():
    """The one game being played right now (None if there isn't one)."""
    live_games = get_games_by_status("live")
    if len(live_games) == 0:
        return None
    return live_games[0]


def get_live_snapshot(advance):
    """
    Work out what the live game looks like right now.

    The database remembers how many events have been played (current_step).
    When advance is True we move on to the next event first, which is how
    the page updates itself while you watch it.
    """
    game = get_live_game()
    if game is None:
        return None

    events = database.query_all(
        "SELECT * FROM live_events WHERE game_id = ? ORDER BY minute", (game["id"],)
    )
    state = database.query_one(
        "SELECT current_step FROM live_state WHERE game_id = ?", (game["id"],)
    )
    step = state["current_step"]

    if advance:
        step = step + 1
        # When we reach the end of the game we start the period again.
        if step > len(events) - 1:
            step = 2
        database.run_command(
            "UPDATE live_state SET current_step = ? WHERE game_id = ?",
            (step, game["id"]),
        )

    current = events[step]
    previous = events[step - 1]

    # Build the list of events the visitor is allowed to see so far.
    shown = []
    for index in range(step + 1):
        event = events[index]
        shown.append({
            "minute": event["minute"],
            "label": event["label"],
            "home_prob": event["home_prob"],
        })

    return {
        "game_id": game["id"],
        "home_team": game["home"],
        "away_team": game["away"],
        "home_abbr": game["home"]["abbr"],
        "away_abbr": game["away"]["abbr"],
        "home_prob": current["home_prob"],
        "away_prob": 100 - current["home_prob"],
        "home_score": current["home_score"],
        "away_score": current["away_score"],
        "minute": current["minute"],
        "event_label": current["label"],
        "change": current["home_prob"] - previous["home_prob"],
        "events": shown,
        "total_events": len(events),
    }


def get_leaderboard():
    """
    Build the leaderboard by adding up every member's finished picks.

    Members are sorted by total points, highest first.
    """
    # Score any picks whose game has finished since the last time we looked.
    connection = database.get_connection()
    scoring.settle_predictions(connection)
    connection.close()

    rows = database.query_all(
        """SELECT users.id, users.username, users.hue,
                  COUNT(predictions.id) AS total_picks,
                  SUM(predictions.is_correct) AS correct_picks,
                  SUM(predictions.points) AS points
           FROM users
           JOIN predictions ON predictions.user_id = users.id
           WHERE predictions.is_correct IS NOT NULL
           GROUP BY users.id
           ORDER BY points DESC, correct_picks DESC"""
    )

    board = []
    rank = 1
    for row in rows:
        # Get this member's results newest first so we can find the streak.
        recent = database.query_all(
            """SELECT is_correct FROM predictions
               WHERE user_id = ? AND is_correct IS NOT NULL
               ORDER BY id DESC""",
            (row["id"],),
        )
        results = []
        for pick in recent:
            results.append(pick["is_correct"])

        accuracy = round(row["correct_picks"] / row["total_picks"] * 100, 1)

        board.append({
            "rank": rank,
            "user_id": row["id"],
            "username": row["username"],
            "hue": row["hue"],
            "initials": row["username"][:2].upper(),
            "accuracy": accuracy,
            "streak": scoring.count_streak(results),
            "points": row["points"],
            "total_picks": row["total_picks"],
            "correct_picks": row["correct_picks"],
        })
        rank = rank + 1

    return board


def get_comments(game_id):
    """Get the discussion messages for one game, newest first."""
    rows = database.query_all(
        """SELECT comments.*, users.username, users.hue,
                  (SELECT COUNT(*) FROM comment_likes
                   WHERE comment_likes.comment_id = comments.id) AS extra_likes
           FROM comments
           JOIN users ON users.id = comments.user_id
           WHERE comments.game_id = ?
           ORDER BY comments.id DESC""",
        (game_id,),
    )

    user_id = session.get("user_id")
    comments = []
    for row in rows:
        # Has the member who is logged in already liked this message?
        liked = False
        if user_id is not None:
            match = database.query_one(
                "SELECT 1 FROM comment_likes WHERE comment_id = ? AND user_id = ?",
                (row["id"], user_id),
            )
            liked = match is not None

        comments.append({
            "id": row["id"],
            "username": row["username"],
            "initials": row["username"][:2].upper(),
            "hue": row["hue"],
            "body": row["body"],
            "pick": row["pick"],
            "likes": row["base_likes"] + row["extra_likes"],
            "liked_by_me": liked,
            "posted_on": row["posted_on"],
        })

    return comments


def get_my_pick(game_id):
    """The team the logged in member picked for a game, or None."""
    user_id = session.get("user_id")
    if user_id is None:
        return None

    row = database.query_one(
        "SELECT picked_team_id FROM predictions WHERE user_id = ? AND game_id = ?",
        (user_id, game_id),
    )
    if row is None:
        return None
    return row["picked_team_id"]


def is_logged_in():
    """True when somebody is signed in."""
    return session.get("user_id") is not None


@app.context_processor
def add_shared_values():
    """
    Anything returned here can be used inside every template,
    so we do not have to pass the same values into every page.
    """
    return {
        "current_user": session.get("username"),
        "logged_in": is_logged_in(),
        "this_year": datetime.now().year,
    }


# ===========================================================
# PAGES
# ===========================================================

@app.route("/")
def home():
    """The home page: hero, the live game and the first few predictions."""
    return render_template(
        "index.html",
        live=get_live_snapshot(False),
        games=get_games_by_status("upcoming")[:3],
        top_members=get_leaderboard()[:3],
        total_games=len(get_games_by_status("final")),
    )


@app.route("/games")
def games_page():
    """Every upcoming game with its prediction, odds and confidence."""
    games = get_games_by_status("upcoming")

    # Show the member which team they have already picked.
    for game in games:
        game["my_pick"] = get_my_pick(game["id"])

    return render_template("games.html", games=games)


@app.route("/matchups")
@app.route("/matchups/<int:game_id>")
def matchups_page(game_id=None):
    """Compare the two teams in a game stat by stat."""
    games = get_games_by_status("upcoming")
    if len(games) == 0:
        abort(404)

    # No game chosen in the address bar, so show the first one.
    if game_id is None:
        game = games[0]
    else:
        game = get_game(game_id)
        if game is None:
            abort(404)

    # Work out the bar widths and which team wins each stat.
    rows = []
    for column, label, biggest, unit in STAT_ROWS:
        home_value = game["home"][column]
        away_value = game["away"][column]

        # For goals against a smaller number is better.
        if column == "goals_against":
            home_wins = home_value < away_value
        else:
            home_wins = home_value > away_value

        rows.append({
            "label": label,
            "unit": unit,
            "home_value": tidy_number(home_value),
            "away_value": tidy_number(away_value),
            "home_width": round(home_value / biggest * 100),
            "away_width": round(away_value / biggest * 100),
            "home_wins": home_wins,
        })

    return render_template("matchups.html", games=games, game=game, stat_rows=rows)


@app.route("/leaderboard")
def leaderboard_page():
    """The community leaderboard, worked out from everybody's picks."""
    board = get_leaderboard()

    # Find the row belonging to the member who is signed in.
    my_row = None
    for member in board:
        if member["user_id"] == session.get("user_id"):
            my_row = member

    pending = 0
    if is_logged_in():
        row = database.query_one(
            """SELECT COUNT(*) AS waiting FROM predictions
               WHERE user_id = ? AND is_correct IS NULL""",
            (session["user_id"],),
        )
        pending = row["waiting"]

    return render_template(
        "leaderboard.html",
        board=board,
        podium=board[:3],
        my_row=my_row,
        pending=pending,
    )


@app.route("/discussion")
@app.route("/discussion/<int:game_id>")
def discussion_page(game_id=None):
    """Read and post messages about a game."""
    games = get_games_by_status("upcoming")
    if len(games) == 0:
        abort(404)

    if game_id is None:
        game = games[0]
    else:
        game = get_game(game_id)
        if game is None:
            abort(404)

    return render_template(
        "discussion.html",
        games=games,
        game=game,
        comments=get_comments(game["id"]),
    )


# ===========================================================
# ACTIONS (forms that send data to the server)
# ===========================================================

@app.route("/discussion/<int:game_id>/post", methods=["POST"])
def post_comment(game_id):
    """Save a new discussion message."""
    if not is_logged_in():
        flash("Please sign in before posting a message.", "error")
        return redirect(url_for("login"))

    game = get_game(game_id)
    if game is None:
        abort(404)

    body = request.form.get("body", "").strip()
    pick = request.form.get("pick", "home")

    # Simple checks so we never save an empty or silly message.
    if body == "":
        flash("Your message was empty, so it was not posted.", "error")
    elif len(body) > 500:
        flash("Messages have to be shorter than 500 characters.", "error")
    else:
        if pick != "home" and pick != "away":
            pick = "home"

        database.run_command(
            """INSERT INTO comments (game_id, user_id, body, pick, posted_on)
               VALUES (?, ?, ?, ?, ?)""",
            (game_id, session["user_id"], body, pick,
             datetime.now().strftime("%Y-%m-%d")),
        )
        flash("Your message was posted.", "success")

    return redirect(url_for("discussion_page", game_id=game_id))


@app.route("/comment/<int:comment_id>/like", methods=["POST"])
def like_comment(comment_id):
    """Like a message, or take the like back if it was already liked."""
    if not is_logged_in():
        flash("Please sign in to like a message.", "error")
        return redirect(url_for("login"))

    comment = database.query_one("SELECT * FROM comments WHERE id = ?", (comment_id,))
    if comment is None:
        abort(404)

    user_id = session["user_id"]
    already = database.query_one(
        "SELECT 1 FROM comment_likes WHERE comment_id = ? AND user_id = ?",
        (comment_id, user_id),
    )

    if already is None:
        database.run_command(
            "INSERT INTO comment_likes (comment_id, user_id) VALUES (?, ?)",
            (comment_id, user_id),
        )
    else:
        database.run_command(
            "DELETE FROM comment_likes WHERE comment_id = ? AND user_id = ?",
            (comment_id, user_id),
        )

    return redirect(url_for("discussion_page", game_id=comment["game_id"]))


@app.route("/predict/<int:game_id>", methods=["POST"])
def make_prediction(game_id):
    """Save the member's pick for an upcoming game."""
    if not is_logged_in():
        flash("Please sign in to save a pick.", "error")
        return redirect(url_for("login"))

    game = get_game(game_id)
    if game is None:
        abort(404)

    if game["status"] != "upcoming":
        flash("That game has already started, so picks are closed.", "error")
        return redirect(url_for("games_page"))

    team_id = request.form.get("team_id", "")
    if not team_id.isdigit():
        flash("Please choose a team.", "error")
        return redirect(url_for("games_page"))

    team_id = int(team_id)
    if team_id != game["home"]["id"] and team_id != game["away"]["id"]:
        flash("That team is not playing in this game.", "error")
        return redirect(url_for("games_page"))

    user_id = session["user_id"]
    existing = get_my_pick(game_id)

    if existing is None:
        database.run_command(
            """INSERT INTO predictions (user_id, game_id, picked_team_id, made_on)
               VALUES (?, ?, ?, ?)""",
            (user_id, game_id, team_id, datetime.now().strftime("%Y-%m-%d")),
        )
    else:
        database.run_command(
            "UPDATE predictions SET picked_team_id = ? WHERE user_id = ? AND game_id = ?",
            (team_id, user_id, game_id),
        )

    picked_team = get_team(team_id)
    flash("Pick saved: " + picked_team["full_name"] + ".", "success")
    return redirect(url_for("games_page"))


# ===========================================================
# MEMBER ACCOUNTS
# ===========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    """Create a new account."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        # Check the details before we save anything.
        if len(username) < 3:
            flash("Your username needs at least 3 characters.", "error")
        elif len(password) < 6:
            flash("Your password needs at least 6 characters.", "error")
        elif password != confirm:
            flash("The two passwords do not match.", "error")
        elif database.query_one("SELECT 1 FROM users WHERE username = ?", (username,)):
            flash("That username is already taken.", "error")
        else:
            # The password is hashed, so the real password is never stored.
            user_id = database.run_command(
                """INSERT INTO users (username, password_hash, hue, joined_on)
                   VALUES (?, ?, ?, ?)""",
                (username, generate_password_hash(password),
                 len(username) * 37 % 360, datetime.now().strftime("%Y-%m-%d")),
            )
            session["user_id"] = user_id
            session["username"] = username
            flash("Welcome to WinThePuck, " + username + "!", "success")
            return redirect(url_for("games_page"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Sign in to an existing account."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = database.query_one("SELECT * FROM users WHERE username = ?", (username,))

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Wrong username or password.", "error")
        else:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Signed in as " + user["username"] + ".", "success")
            return redirect(url_for("home"))

    return render_template("login.html", demo_password=DEMO_PASSWORD_HINT)


@app.route("/logout")
def logout():
    """Sign out and clear the session."""
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


# ===========================================================
# JSON API (used by the JavaScript on the pages)
# ===========================================================

@app.route("/api/games")
def api_games():
    """Send every upcoming game as JSON."""
    return jsonify(get_games_by_status("upcoming"))


@app.route("/api/live")
def api_live():
    """
    Send the live game as JSON and move it on by one event.
    main.js calls this every few seconds so the chart keeps updating.
    """
    snapshot = get_live_snapshot(True)
    if snapshot is None:
        return jsonify({"error": "No live game right now"}), 404
    return jsonify(snapshot)


@app.route("/api/leaderboard")
def api_leaderboard():
    """Send the leaderboard as JSON."""
    return jsonify(get_leaderboard())


# ===========================================================
# ERROR PAGES
# ===========================================================

@app.errorhandler(404)
def page_not_found(error):
    """Shown when somebody types an address that does not exist."""
    return render_template("404.html"), 404


if __name__ == "__main__":
    # Stop with a clear message instead of a crash if the database is missing.
    if not database.database_exists():
        print("The database has not been built yet.")
        print("Please run this first:  python seed_data.py")
    else:
        app.run(debug=True)
