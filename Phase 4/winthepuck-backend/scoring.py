"""
WinThePuck - scoring the members' picks
Phase 4: Back End Development

The leaderboard is built from the picks members make. This file holds
the rules for turning a finished game into points, so both app.py and
seed_data.py score picks in exactly the same way.
"""

# Points given out once a game is over.
POINTS_FOR_CORRECT = 100
POINTS_FOR_WRONG = 10


def settle_predictions(connection):
    """
    Look at every pick that has not been scored yet. If the game it
    belongs to has finished, decide whether the pick was right and
    give the member their points.

    Returns how many picks were scored.
    """
    waiting = connection.execute(
        """SELECT predictions.id, predictions.picked_team_id, games.winner_team_id
           FROM predictions
           JOIN games ON games.id = predictions.game_id
           WHERE predictions.is_correct IS NULL AND games.status = 'final'"""
    ).fetchall()

    for pick in waiting:
        if pick["picked_team_id"] == pick["winner_team_id"]:
            is_correct = 1
            points = POINTS_FOR_CORRECT
        else:
            is_correct = 0
            points = POINTS_FOR_WRONG

        connection.execute(
            "UPDATE predictions SET is_correct = ?, points = ? WHERE id = ?",
            (is_correct, points, pick["id"]),
        )

    connection.commit()
    return len(waiting)


def count_streak(results):
    """
    Count how many picks a member has got right in a row.

    The list is newest first, so we stop counting at the first wrong pick.
    """
    streak = 0
    for result in results:
        if result == 1:
            streak = streak + 1
        else:
            break
    return streak
