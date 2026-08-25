"""The maths behind the model health page.

These are pure functions with no database and no network, so they can be
checked against cases where the right answer is known in advance - a perfect
forecaster, a useless one, a liar. That is much stronger evidence than
checking the number the live data happens to produce today.
"""
from __future__ import annotations

import math

import pytest

import metrics

# ===========================================================
# ACCURACY
# ===========================================================

def test_accuracy_counts_the_side_the_model_leaned_towards():
    assert metrics.accuracy([(0.9, 1), (0.8, 1)]) == 100.0
    assert metrics.accuracy([(0.9, 0), (0.8, 0)]) == 0.0
    # Under 0.5 the model is picking the away team, so an away win is a hit.
    assert metrics.accuracy([(0.2, 0), (0.3, 0)]) == 100.0
    assert metrics.accuracy([]) is None


# ===========================================================
# BRIER AND LOG LOSS
# ===========================================================

def test_a_perfect_forecaster_scores_zero():
    assert metrics.brier_score([(1.0, 1), (0.0, 0)]) == 0.0


def test_always_saying_fifty_fifty_scores_a_quarter():
    """0.25 is the Brier score of somebody who refuses to commit."""
    assert metrics.brier_score([(0.5, 1), (0.5, 0)]) == 0.25


def test_log_loss_beats_the_coin_flip_only_by_being_informative():
    coin_flip = metrics.log_loss([(0.5, 1), (0.5, 0)])
    assert coin_flip == pytest.approx(math.log(2), abs=1e-4)
    assert coin_flip == metrics.baseline_log_loss()

    informed = metrics.log_loss([(0.8, 1), (0.2, 0)])
    assert informed < coin_flip


def test_log_loss_punishes_confident_mistakes_hard():
    mild = metrics.log_loss([(0.6, 0)])
    confident = metrics.log_loss([(0.99, 0)])
    assert confident > mild * 4


def test_a_certain_wrong_answer_stays_a_finite_number():
    """
    Being 100% sure and wrong is mathematically infinite.

    The probabilities are clamped just short of 0 and 1 so one bad prediction
    cannot turn the whole page into "inf".
    """
    assert math.isfinite(metrics.log_loss([(1.0, 0)]))
    assert metrics.log_loss([(1.0, 0)]) > 30


def test_empty_input_gives_nothing_rather_than_crashing():
    assert metrics.brier_score([]) is None
    assert metrics.log_loss([]) is None
    assert metrics.expected_calibration_error([]) is None


# ===========================================================
# CALIBRATION
# ===========================================================

def test_an_honest_forecaster_has_almost_no_calibration_error():
    """Says 70% on 100 games and wins exactly 70 of them."""
    pairs = [(0.7, 1)] * 70 + [(0.7, 0)] * 30
    assert metrics.expected_calibration_error(pairs) < 1.0


def test_a_boastful_forecaster_is_caught():
    """Says 90% on 100 games and only wins half of them."""
    pairs = [(0.9, 1)] * 50 + [(0.9, 0)] * 50
    assert metrics.expected_calibration_error(pairs) > 35


def test_the_reliability_curve_folds_both_sides_onto_confidence():
    """
    Saying "home has 20%" is the same statement as "away has 80%".

    Both are an 80% call, so both belong in the same row of the table - and
    both are correct when the away team wins.
    """
    curve = metrics.reliability_curve([(0.2, 0), (0.8, 1)], bins=10)
    row = next(r for r in curve if r["games"])
    assert row["games"] == 2
    assert row["predicted"] == pytest.approx(80.0, abs=0.1)
    assert row["actual"] == 100.0


def test_the_reliability_curve_always_returns_every_band():
    curve = metrics.reliability_curve([(0.9, 1)], bins=10)
    assert len(curve) == 10
    assert sum(row["games"] for row in curve) == 1
    # Empty bands are reported as empty rather than dropped, so the table on
    # the page keeps the same shape from one week to the next.
    assert any(row["games"] == 0 and row["predicted"] is None for row in curve)


# ===========================================================
# DRIFT
# ===========================================================

def test_a_distribution_has_not_drifted_from_itself():
    values = [0.3, 0.45, 0.5, 0.55, 0.7, 0.9] * 10
    assert metrics.population_stability_index(values, values) == 0.0


def test_a_clear_shift_is_reported_as_a_large_psi():
    timid = [0.5] * 200
    bold = [0.95] * 200
    assert metrics.population_stability_index(timid, bold) > metrics.PSI_MODERATE


def test_psi_thresholds_read_the_way_the_industry_reads_them():
    assert metrics.drift_verdict(0.05) == "stable"
    assert metrics.drift_verdict(0.15) == "watch"
    assert metrics.drift_verdict(0.40) == "shifted"
    assert metrics.drift_verdict(None) == "unknown"


def test_psi_needs_both_sides_to_be_present():
    assert metrics.population_stability_index([], [0.5]) is None
    assert metrics.population_stability_index([0.5], []) is None


def test_drift_is_not_reported_on_a_handful_of_games():
    """
    A quiet week is not a crisis.

    Without this guard the page would announce that the model had shifted
    every time the schedule got short, which is the fastest way to teach
    somebody to ignore a monitoring page.
    """
    report = metrics.drift_report([0.5] * 500, [0.9] * 5)
    assert report["verdict"] == "unknown"
    assert report["psi"] is None


def test_a_short_slate_is_labelled_provisional():
    report = metrics.drift_report([0.5] * 500, [0.9] * 40)
    assert report["psi"] is not None
    assert report["provisional"] is True

    settled = metrics.drift_report([0.5] * 500, [0.9] * 200)
    assert settled["provisional"] is False


# ===========================================================
# PUTTING IT TOGETHER
# ===========================================================

def test_a_small_sample_says_so_instead_of_guessing():
    summary = metrics.summarise([(0.6, 1)] * 5)
    assert summary["enough"] is False
    assert summary["needed"] == metrics.MIN_SAMPLE
    assert "accuracy" not in summary


def test_a_full_summary_carries_every_figure_the_page_shows():
    summary = metrics.summarise([(0.7, 1), (0.3, 0)] * 25)
    assert summary["enough"] is True
    for key in ("accuracy", "brier", "logLoss", "ece", "reliability"):
        assert key in summary


def test_live_results_are_compared_against_the_published_baseline():
    reference = metrics.summarise([(0.7, 1)] * 60 + [(0.7, 0)] * 40)   # 60%
    on_track = metrics.summarise([(0.7, 1)] * 59 + [(0.7, 0)] * 41)
    collapsed = metrics.summarise([(0.7, 1)] * 30 + [(0.7, 0)] * 70)

    assert metrics.compare(on_track, reference)["status"] == "on-track"
    assert metrics.compare(collapsed, reference)["status"] == "below-baseline"
    # Too few live games to judge yet.
    assert metrics.compare(metrics.summarise([(0.7, 1)] * 3),
                           reference)["status"] == "warming-up"
