"""Turning finished games into leaderboard points.

Both the first-time setup and the live website score picks through here, so
there is only ever one set of rules.
"""
from __future__ import annotations

import sqlite3

import config


def settle_predictions(connection: sqlite3.Connection) -> int:
    """
    Score every pick whose game has finished since we last looked.

    A correct pick is worth 100 points. A wrong one still earns 10, so that
    somebody who plays every night is not punished for taking part.
    """
    waiting = connection.execute(
        """SELECT predictions.id, predictions.picked_team_id, games.winner_team_id
           FROM predictions
           JOIN games ON games.id = predictions.game_id
           WHERE predictions.is_correct IS NULL
             AND games.status = 'final'
             AND games.winner_team_id IS NOT NULL"""
    ).fetchall()

    for pick in waiting:
        correct = pick["picked_team_id"] == pick["winner_team_id"]
        connection.execute(
            "UPDATE predictions SET is_correct = ?, points = ? WHERE id = ?",
            (1 if correct else 0,
             config.POINTS_FOR_CORRECT if correct else config.POINTS_FOR_WRONG,
             pick["id"]),
        )

    connection.commit()
    return len(waiting)


def count_streak(results: list[int]) -> int:
    """
    How many picks in a row a member has got right.

    The list arrives newest first, so we stop at the first wrong pick.
    """
    streak = 0
    for result in results:
        if result != 1:
            break
        streak += 1
    return streak
