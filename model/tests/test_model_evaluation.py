"""The evaluation study, and the rule that stops it fooling itself.

The whole point of `evaluate_model.py` is to give an honest answer about
whether a change helps. That only works if two things hold: the maths is
right, and the held-out season is genuinely held out. Both are checked here.
"""
from __future__ import annotations

import math

import pytest

import evaluate_model as study


def row(season, y, ensemble, hgb=None, logit=None, catboost=None, elo=None,
        game_id=1, game_date="2025-10-01"):
    return {
        "season": season, "y": y, "ensemble": ensemble,
        "p_hgb": hgb if hgb is not None else ensemble,
        "p_logit": logit if logit is not None else ensemble,
        "p_catboost": catboost if catboost is not None else ensemble,
        "elo": elo if elo is not None else ensemble,
        "game_id": game_id, "game_date": game_date,
    }


# ===========================================================
# THE MATHS
# ===========================================================

def test_logit_and_sigmoid_undo_each_other():
    for probability in (0.01, 0.25, 0.5, 0.75, 0.99):
        assert study.sigmoid(study.logit(probability)) == pytest.approx(
            probability, abs=1e-9)


def test_sigmoid_survives_extreme_input():
    """
    Written in two branches so a very negative input cannot overflow.

    The naive 1/(1+exp(-z)) raises OverflowError somewhere around z = -746,
    which a confident model can reach.
    """
    assert study.sigmoid(-1000) == pytest.approx(0.0, abs=1e-9)
    assert study.sigmoid(1000) == pytest.approx(1.0, abs=1e-9)
    assert study.sigmoid(0) == 0.5


def test_log_loss_matches_the_textbook():
    assert study.log_loss([(0.5, 1), (0.5, 0)]) == pytest.approx(math.log(2), abs=1e-6)
    assert study.log_loss([(0.9, 1)]) == pytest.approx(-math.log(0.9), abs=1e-6)


def test_a_certain_wrong_answer_stays_finite():
    assert math.isfinite(study.log_loss([(1.0, 0)]))


def test_brier_and_accuracy():
    assert study.brier([(1.0, 1), (0.0, 0)]) == 0.0
    assert study.brier([(0.5, 1), (0.5, 0)]) == 0.25
    assert study.accuracy([(0.9, 1), (0.1, 0)]) == 100.0
    assert study.accuracy([(0.9, 0), (0.1, 1)]) == 0.0


# ===========================================================
# THE SPLIT
# ===========================================================

def test_the_held_out_season_is_kept_out_of_the_training_half():
    """
    This is the rule the whole study rests on.

    If a single game from the held-out season leaked into the tuning set,
    every "improvement" the script reported would be worthless.
    """
    rows = ([row(20222023, 1, 0.6)] * 3
            + [row(20242025, 0, 0.4)] * 2
            + [row(study.HELD_OUT_SEASON, 1, 0.7)] * 4)
    train, test = study.split(rows)

    assert len(train) == 5
    assert len(test) == 4
    assert all(r["season"] < study.HELD_OUT_SEASON for r in train)
    assert all(r["season"] == study.HELD_OUT_SEASON for r in test)


# ===========================================================
# THE ADAPTIVE CORRECTION
# ===========================================================

def test_the_home_ice_correction_only_ever_looks_backwards():
    """
    A game must never be adjusted using its own result.

    With a window longer than the data, no adjustment is possible at all, so
    the probabilities have to come back exactly as they went in. If any part
    of the correction were peeking at the current row, this would drift.
    """
    rows = [row(20222023, index % 2, 0.6, game_id=index) for index in range(10)]
    out = study.adaptive_home_ice(rows, window=50, strength=1.0)
    assert [p for p, _ in out] == pytest.approx([0.6] * 10)


def test_the_correction_moves_predictions_once_it_has_enough_history():
    # Home teams winning everything should push later predictions upwards.
    rows = [row(20222023, 1, 0.5, game_id=index) for index in range(20)]
    out = study.adaptive_home_ice(rows, window=5, strength=1.0)
    assert out[-1][0] > 0.5


def test_the_outcomes_are_carried_through_untouched():
    rows = [row(20222023, index % 2, 0.6, game_id=index) for index in range(8)]
    out = study.adaptive_home_ice(rows, window=3, strength=0.5)
    assert [y for _, y in out] == [r["y"] for r in rows]


# ===========================================================
# THE VERDICT
# ===========================================================

def test_a_tiny_gain_is_called_noise_rather_than_an_improvement():
    """
    The trap this is guarding against.

    Every candidate tried in this study gained about 0.0004 log loss. On 1,394
    coin-flip-ish hockey games that is nothing, and calling it a win would be
    exactly the mistake the study exists to avoid.
    """
    baseline = {"logLoss": 0.6857, "brier": 0.2463, "accuracy": 55.4, "games": 1394}
    barely_better = {"heldOut": {"logLoss": 0.6853}}
    verdict = study.verdict(barely_better, baseline)

    assert verdict["helped"] is False
    assert "noise" in verdict["note"]


def test_a_real_gain_is_recognised():
    baseline = {"logLoss": 0.6857, "brier": 0.2463, "accuracy": 55.4, "games": 1394}
    much_better = {"heldOut": {"logLoss": 0.6600}}
    assert study.verdict(much_better, baseline)["helped"] is True


def test_a_clear_regression_is_called_out():
    baseline = {"logLoss": 0.6857, "brier": 0.2463, "accuracy": 55.4, "games": 1394}
    worse = {"heldOut": {"logLoss": 0.7100}}
    verdict = study.verdict(worse, baseline)
    assert verdict["helped"] is False
    assert "worse" in verdict["note"]


# ===========================================================
# THE WHOLE STUDY, ON THE REAL DATA
# ===========================================================

@pytest.fixture(scope="module")
def real_rows():
    if not study.DEFAULT_PREDICTIONS.exists():
        pytest.skip("the walk-forward predictions are not in this checkout")
    return study.load(study.DEFAULT_PREDICTIONS)


def test_the_walk_forward_file_is_the_one_the_report_quotes(real_rows):
    assert len(real_rows) == 5592
    assert len({r["season"] for r in real_rows}) == 4


def test_the_per_season_table_shows_the_model_ageing(real_rows):
    """
    The finding the study actually landed on.

    Accuracy falls and the spread of the predictions narrows as the model gets
    further from its training data. That is the case for retraining, and the
    reason the monitoring page exists.
    """
    seasons = study.per_season(real_rows)
    assert [s["season"] for s in seasons] == sorted(s["season"] for s in seasons)

    first, last = seasons[0], seasons[-1]
    assert first["accuracy"] > last["accuracy"]
    assert first["spread"] > last["spread"]


@pytest.mark.slow
def test_none_of_the_candidates_survive_the_held_out_season(real_rows):
    """
    Locks in the conclusion.

    If somebody later changes the model and one of these candidates starts
    genuinely helping, this test fails and asks to be looked at - which is
    what it is for.
    """
    report = study.build_report(real_rows)
    assert report["baseline"]["heldOut"]["games"] == 1394
    assert all(c["verdict"]["helped"] is False for c in report["candidates"])
