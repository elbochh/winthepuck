"""
WinThePuck - fill the database with starting data
Phase 4: Back End Development

Run this file once before starting the website:

    python seed_data.py

It creates winthepuck.db, builds all of the tables and adds the teams,
games, members, picks and discussion messages the website needs.
"""

from datetime import datetime

from werkzeug.security import generate_password_hash

import database
import scoring

# Every demo member uses this password so the marker can log in and test.
DEMO_PASSWORD = "puck1234"


# ===========================================================
# 1) THE DATA WE WANT IN THE DATABASE
# ===========================================================

# abbr, city, name, colour, record, GF, GA, PP%, PK%, shots, faceoff%, last 5
TEAMS = [
    ("TBL", "Tampa Bay", "Lightning",      "#3b82f6", "31-18-5", 3.3, 2.9, 24, 79, 32, 51, "W,L,W,W,L"),
    ("EDM", "Edmonton",  "Oilers",         "#f97316", "34-16-4", 3.4, 2.7, 25, 81, 33, 52, "W,W,L,W,O"),
    ("COL", "Colorado",  "Avalanche",      "#7c3aed", "36-14-3", 3.7, 2.5, 28, 82, 35, 54, "W,W,O,W,W"),
    ("FLA", "Florida",   "Panthers",       "#ef4444", "33-17-4", 3.5, 2.6, 26, 83, 33, 53, "W,W,W,O,W"),
    ("BOS", "Boston",    "Bruins",         "#eab308", "29-19-6", 2.9, 2.8, 20, 81, 29, 52, "L,W,O,L,W"),
    ("NYR", "New York",  "Rangers",        "#2563eb", "32-17-4", 3.1, 2.5, 23, 84, 30, 49, "W,W,L,W,W"),
    ("VGK", "Vegas",     "Golden Knights", "#d4af37", "30-18-5", 3.0, 2.9, 21, 78, 31, 48, "L,W,L,O,W"),
    ("DAL", "Dallas",    "Stars",          "#16a34a", "35-15-3", 3.6, 2.4, 27, 85, 34, 55, "W,W,W,W,L"),
]

# time, home, away, home win %, confidence, home odds, away odds
UPCOMING_GAMES = [
    ("Sat 7:00 PM",  "TBL", "FLA", 48, 72,  118, -135),
    ("Sat 9:30 PM",  "NYR", "BOS", 58, 65, -140,  122),
    ("Sat 10:00 PM", "VGK", "DAL", 44, 81,  134, -155),
    ("Sat 11:00 PM", "COL", "TBL", 63, 69, -165,  142),
]

# The one game that is being played right now.
LIVE_GAME = ("2nd Period", "EDM", "COL", 61, 70, -150, 130)

# minute, what happened, EDM win probability, home goals, away goals
LIVE_EVENTS = [
    (0,  "Puck drop",            54, 0, 0),
    (6,  "EDM goal - McDavid",   63, 1, 0),
    (13, "COL power play",       55, 1, 0),
    (18, "COL goal - MacKinnon", 47, 1, 1),
    (24, "EDM goal - Draisaitl", 60, 2, 1),
    (31, "EDM penalty kill",     58, 2, 1),
    (38, "EDM hits crossbar",    61, 2, 1),
]

# Games that have already been played. The leaderboard is worked out
# from the picks members made on these games.
# date, home, away, home goals, away goals
FINISHED_GAMES = [
    ("Feb 01", "EDM", "BOS", 4, 2),
    ("Feb 02", "COL", "VGK", 3, 1),
    ("Feb 03", "FLA", "NYR", 2, 5),
    ("Feb 05", "DAL", "TBL", 4, 3),
    ("Feb 06", "BOS", "COL", 1, 4),
    ("Feb 08", "NYR", "EDM", 3, 2),
    ("Feb 09", "TBL", "VGK", 5, 2),
    ("Feb 11", "VGK", "FLA", 2, 3),
    ("Feb 12", "DAL", "COL", 2, 4),
    ("Feb 14", "EDM", "TBL", 6, 3),
    ("Feb 15", "BOS", "NYR", 2, 1),
    ("Feb 17", "FLA", "DAL", 3, 2),
    ("Feb 18", "COL", "EDM", 5, 4),
    ("Feb 20", "TBL", "BOS", 4, 1),
    ("Feb 21", "NYR", "VGK", 3, 0),
    ("Feb 23", "DAL", "FLA", 1, 2),
    ("Feb 24", "VGK", "EDM", 2, 5),
    ("Feb 26", "COL", "NYR", 4, 2),
    ("Feb 27", "BOS", "DAL", 3, 4),
    ("Mar 01", "FLA", "TBL", 2, 3),
]

# username, avatar colour, how many of the finished games they picked,
# how many they got right, how long their current winning streak is
MEMBERS = [
    ("FrozenOracle",     190, 20, 15, 5),
    ("TwineTimeTom",      90, 20, 14, 3),
    ("IceColdAnalytics", 200, 19, 13, 2),
    ("BlueLineBetty",     40, 18, 12, 4),
    ("SlapshotSam",      120, 17, 10, 0),
    ("PuckLuck99",       280, 16,  9, 1),
]

# who wrote it, what they said, who they picked, starting likes
STARTING_COMMENTS = [
    ("SlapshotSam",      "Panthers PK has been elite lately. Taking the road dog with confidence here.",       "away", 34),
    ("IceColdAnalytics", "Model loves Tampa at home but their goaltending splits worry me. Live betting only.", "home", 21),
    ("PuckLuck99",       "Back-to-back for Florida, fatigue is real. Lightning steal this one in OT.",          "home", 12),
    ("BlueLineBetty",    "Faceoff win % gap is the tell. Cats control possession and grind it out.",            "away", 47),
]


# ===========================================================
# 2) HELPER FUNCTIONS
# ===========================================================

def today():
    """Return today's date as text, for example "2026-08-10"."""
    return datetime.now().strftime("%Y-%m-%d")


def build_result_list(total_picks, wins, streak):
    """
    Build a list of 1s (correct pick) and 0s (wrong pick).

    The list is in date order, oldest first, and the current winning
    streak is put at the very end so it is the member's latest form.
    """
    losses = total_picks - wins

    # Start with the streak of wins that sits at the end of the list.
    ending = []
    for i in range(streak):
        ending.append(1)

    # A loss goes just in front of the streak. It stops the older picks
    # from running into the streak and making it longer than we asked for.
    if losses > 0:
        ending.insert(0, 0)
        losses = losses - 1

    wins_left = wins - streak

    # Now fill the older picks, mixing wins and losses so the results
    # do not look like one long block.
    beginning = []
    while wins_left > 0 or losses > 0:
        if wins_left > 0:
            beginning.append(1)
            wins_left = wins_left - 1
        if losses > 0:
            beginning.append(0)
            losses = losses - 1

    return beginning + ending


# ===========================================================
# 3) FILLING EACH TABLE
# ===========================================================

def add_teams(connection):
    """Add all of the NHL teams and return a lookup of abbr -> id."""
    team_ids = {}
    for team in TEAMS:
        cursor = connection.execute(
            """INSERT INTO teams
               (abbr, city, name, color, record, goals_for, goals_against,
                power_play, penalty_kill, shots_per_game, faceoff_win, recent_form)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            team,
        )
        team_ids[team[0]] = cursor.lastrowid
    print("Added " + str(len(TEAMS)) + " teams")
    return team_ids


def add_games(connection, team_ids):
    """Add the upcoming games, the live game and the finished games."""
    # --- upcoming games ---
    for game_time, home, away, prob, confidence, home_odds, away_odds in UPCOMING_GAMES:
        connection.execute(
            """INSERT INTO games
               (game_time, home_team_id, away_team_id, home_win_prob,
                confidence, home_odds, away_odds, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'upcoming')""",
            (game_time, team_ids[home], team_ids[away], prob,
             confidence, home_odds, away_odds),
        )

    # --- the live game ---
    game_time, home, away, prob, confidence, home_odds, away_odds = LIVE_GAME
    cursor = connection.execute(
        """INSERT INTO games
           (game_time, home_team_id, away_team_id, home_win_prob,
            confidence, home_odds, away_odds, status, home_score, away_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'live', 0, 0)""",
        (game_time, team_ids[home], team_ids[away], prob,
         confidence, home_odds, away_odds),
    )
    live_game_id = cursor.lastrowid

    for minute, label, home_prob, home_score, away_score in LIVE_EVENTS:
        connection.execute(
            """INSERT INTO live_events
               (game_id, minute, label, home_prob, home_score, away_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (live_game_id, minute, label, home_prob, home_score, away_score),
        )

    # The live game starts by showing the first three events.
    connection.execute(
        "INSERT INTO live_state (game_id, current_step) VALUES (?, 2)",
        (live_game_id,),
    )

    # --- finished games ---
    finished_ids = []
    for date, home, away, home_score, away_score in FINISHED_GAMES:
        if home_score > away_score:
            winner = team_ids[home]
        else:
            winner = team_ids[away]

        # A simple model number so the finished games look like the others.
        home_win_prob = 50 + (home_score - away_score) * 4

        cursor = connection.execute(
            """INSERT INTO games
               (game_time, home_team_id, away_team_id, home_win_prob,
                confidence, home_odds, away_odds, status,
                home_score, away_score, winner_team_id)
               VALUES (?, ?, ?, ?, 70, -130, 115, 'final', ?, ?, ?)""",
            (date, team_ids[home], team_ids[away], home_win_prob,
             home_score, away_score, winner),
        )
        finished_ids.append(cursor.lastrowid)

    print("Added " + str(len(UPCOMING_GAMES)) + " upcoming games, 1 live game and "
          + str(len(FINISHED_GAMES)) + " finished games")
    return live_game_id, finished_ids


def add_members(connection):
    """Add the demo members and return a lookup of username -> id."""
    user_ids = {}
    for username, hue, total_picks, wins, streak in MEMBERS:
        cursor = connection.execute(
            """INSERT INTO users (username, password_hash, hue, joined_on)
               VALUES (?, ?, ?, ?)""",
            (username, generate_password_hash(DEMO_PASSWORD), hue, today()),
        )
        user_ids[username] = cursor.lastrowid
    print("Added " + str(len(MEMBERS)) + " members (password for all of them: " + DEMO_PASSWORD + ")")
    return user_ids


def add_predictions(connection, user_ids, finished_ids):
    """Give every demo member a history of picks on the finished games."""
    total_added = 0

    for username, hue, total_picks, wins, streak in MEMBERS:
        results = build_result_list(total_picks, wins, streak)

        for index in range(len(results)):
            game_id = finished_ids[index]
            game = connection.execute(
                "SELECT home_team_id, away_team_id, winner_team_id FROM games WHERE id = ?",
                (game_id,),
            ).fetchone()

            # If this pick should be correct we choose the winning team,
            # otherwise we choose the team that lost.
            if results[index] == 1:
                picked = game["winner_team_id"]
            elif game["winner_team_id"] == game["home_team_id"]:
                picked = game["away_team_id"]
            else:
                picked = game["home_team_id"]

            connection.execute(
                """INSERT INTO predictions
                   (user_id, game_id, picked_team_id, made_on)
                   VALUES (?, ?, ?, ?)""",
                (user_ids[username], game_id, picked, today()),
            )
            total_added = total_added + 1

    # Now that the picks are saved, compare each one with the real result.
    scored = scoring.settle_predictions(connection)
    print("Added " + str(total_added) + " picks and scored " + str(scored) + " of them")


def add_comments(connection, user_ids):
    """Add the starting discussion messages on the first upcoming game."""
    first_game = connection.execute(
        "SELECT id FROM games WHERE status = 'upcoming' ORDER BY id LIMIT 1"
    ).fetchone()

    for username, body, pick, base_likes in STARTING_COMMENTS:
        connection.execute(
            """INSERT INTO comments
               (game_id, user_id, body, pick, base_likes, posted_on)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (first_game["id"], user_ids[username], body, pick, base_likes, today()),
        )
    print("Added " + str(len(STARTING_COMMENTS)) + " discussion messages")


# ===========================================================
# 4) RUN EVERYTHING
# ===========================================================

def main():
    print("Building the WinThePuck database...")
    database.build_database()

    connection = database.get_connection()

    team_ids = add_teams(connection)
    live_game_id, finished_ids = add_games(connection, team_ids)
    user_ids = add_members(connection)
    add_predictions(connection, user_ids, finished_ids)
    add_comments(connection, user_ids)

    connection.commit()
    connection.close()

    print("Done. Now run:  python app.py")


if __name__ == "__main__":
    main()
