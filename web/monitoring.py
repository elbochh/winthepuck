"""Watching the model in production.

The walk-forward test scored the model once and wrote down a score. That score starts going
out of date the moment the model is deployed - the league changes, teams
rebuild, and a model trained on games up to June 2026 slowly drifts away from
the sport it is predicting.

The evaluation study in `model/evaluate_model.py` showed exactly that
happening across the four test seasons: accuracy slid from 59.6% to 55.4%, and
the model's predictions bunched closer and closer to 50% as it aged. It also
showed that no post-hoc correction fixed it. The answer to a model going stale
is not a clever patch - it is noticing, and retraining.

So this file is the noticing. It builds three views out of what the database
already stores, and the /monitoring page puts them on screen:

  Baseline    how the model scored on the season it was tested on. The line
              in the sand everything else is compared against.

  Live        the same numbers for games this deployment predicted itself and
              which have since been played. Silent until enough games have
              been played to mean anything.

  Drift       whether the shape of today's predictions still resembles the
              shape of the ones from testing (PSI).

The maths lives in metrics.py; this file only decides which games go into
which bucket.
"""
from __future__ import annotations

import database
import metrics


def _pairs(rows) -> list[tuple[float, int]]:
    """Turn game rows into the (probability, did the home team win) pairs."""
    return [(row["home_win_prob"] / 100,
             1 if row["winner_team_id"] == row["home_team_id"] else 0)
            for row in rows]


def _probabilities(rows) -> list[float]:
    return [row["home_win_prob"] / 100 for row in rows]


def baseline_season() -> int:
    """
    The season the model's published track record comes from.

    Games from this season were loaded from the walk-forward test.
    Anything from a later season was predicted by this deployment, live.
    """
    label = database.get_meta("history_season", "")
    if label.isdigit():
        return int(label)
    row = database.query_one(
        "SELECT MIN(season) AS s FROM games WHERE status = 'final'")
    return int(row["s"]) if row and row["s"] is not None else 0


def graded_games(season_filter: str, values: tuple = ()) -> list:
    """Every finished game we know the model's pre-game probability for."""
    return database.query_all(
        "SELECT home_win_prob, winner_team_id, home_team_id, game_date, season "
        "FROM games WHERE status = 'final' AND winner_team_id IS NOT NULL "
        + season_filter + " ORDER BY game_date",
        values,
    )


def build_report() -> dict:
    """Everything the /monitoring page and /api/monitoring show."""
    baseline = baseline_season()

    reference_rows = graded_games("AND season <= ?", (baseline,))
    live_rows = graded_games("AND season > ?", (baseline,))
    upcoming_rows = database.query_all(
        "SELECT home_win_prob FROM games WHERE status = 'upcoming'")

    reference = metrics.summarise(_pairs(reference_rows))
    live = metrics.summarise(_pairs(live_rows))

    # Drift is measured on what the model is saying *now* - the slate it has
    # just predicted - against the spread of probabilities it produced during
    # testing. It needs no results, so it is the one signal available on day
    # one, before a single live game has been played.
    reference_probabilities = _probabilities(reference_rows)
    current_probabilities = (_probabilities(upcoming_rows)
                             or _probabilities(live_rows))
    drift = metrics.drift_report(reference_probabilities, current_probabilities)
    drift["thresholds"] = {"stable": metrics.PSI_STABLE,
                           "shifted": metrics.PSI_MODERATE}

    return {
        "baselineSeason": baseline,
        "reference": reference,
        "live": live,
        "comparison": metrics.compare(live, reference),
        "drift": drift,
        "modelTrainedTo": database.get_meta("model_trained_to"),
        "lastRefresh": database.get_meta("last_refresh"),
        "minimumSample": metrics.MIN_SAMPLE,
    }
