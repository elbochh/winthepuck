"""The Elo rating system, which is the strongest single input the model has.

Elo is the part of the pipeline written by hand rather than fitted, so it is
the part where a sign error or a misplaced bracket would quietly poison every
prediction without ever raising an exception. These tests pin down the
properties it has to have.
"""
from __future__ import annotations

import pytest

import elo

# ===========================================================
# THE PROBABILITY CURVE
# ===========================================================

def test_two_equal_teams_are_a_coin_flip():
    assert elo.win_probability(0) == 0.5


def test_a_400_point_lead_is_worth_ten_to_one():
    """The defining property of Elo: 400 points means ten times as likely."""
    assert elo.win_probability(400) == pytest.approx(10 / 11, abs=1e-6)
    assert elo.win_probability(-400) == pytest.approx(1 / 11, abs=1e-6)


def test_the_curve_only_ever_goes_one_way():
    probabilities = [elo.win_probability(d) for d in range(-500, 501, 50)]
    assert probabilities == sorted(probabilities)
    assert all(0 < p < 1 for p in probabilities)


def test_home_ice_is_worth_something_but_not_everything():
    even = elo.matchup_features(elo.TeamState(1500), elo.TeamState(1500))
    assert even["elo_prob_home"] > 0.5
    # 50 Elo points is a real edge, not a guaranteed win.
    assert even["elo_prob_home"] < 0.60


# ===========================================================
# UPDATING AFTER A GAME
# ===========================================================

def test_the_winner_gains_exactly_what_the_loser_drops():
    """Elo is zero-sum. If it were not, ratings would inflate all season."""
    home, away = elo.TeamState(1500), elo.TeamState(1500)
    elo.apply_result(home, away, 4, 1, game_type=2)
    assert home.elo + away.elo == pytest.approx(3000, abs=1e-9)
    assert home.elo > 1500 > away.elo


def test_beating_a_stronger_team_is_worth_more():
    weak_vs_strong = elo.TeamState(1400)
    strong = elo.TeamState(1700)
    elo.apply_result(weak_vs_strong, strong, 3, 2, game_type=2)
    upset_gain = weak_vs_strong.elo - 1400

    expected_home = elo.TeamState(1700)
    expected_away = elo.TeamState(1400)
    elo.apply_result(expected_home, expected_away, 3, 2, game_type=2)
    routine_gain = expected_home.elo - 1700

    assert upset_gain > routine_gain


def test_a_bigger_win_moves_the_rating_further():
    narrow_home, narrow_away = elo.TeamState(1500), elo.TeamState(1500)
    elo.apply_result(narrow_home, narrow_away, 2, 1, game_type=2)

    blowout_home, blowout_away = elo.TeamState(1500), elo.TeamState(1500)
    elo.apply_result(blowout_home, blowout_away, 7, 1, game_type=2)

    assert blowout_home.elo > narrow_home.elo


def test_the_margin_bonus_is_capped():
    """
    A 9-0 win is better than 5-0, but not twice as informative.

    Without the damping, one freak scoreline would distort a team's rating for
    weeks.
    """
    five_nil = elo.TeamState(1500)
    elo.apply_result(five_nil, elo.TeamState(1500), 5, 0, game_type=2)
    nine_nil = elo.TeamState(1500)
    elo.apply_result(nine_nil, elo.TeamState(1500), 9, 0, game_type=2)

    assert nine_nil.elo > five_nil.elo
    assert (nine_nil.elo - 1500) < 1.5 * (five_nil.elo - 1500)


def test_playoff_games_count_for_more():
    regular = elo.TeamState(1500)
    elo.apply_result(regular, elo.TeamState(1500), 3, 1, game_type=2)
    playoff = elo.TeamState(1500)
    elo.apply_result(playoff, elo.TeamState(1500), 3, 1, game_type=3)

    assert playoff.elo - 1500 == pytest.approx(
        (regular.elo - 1500) * elo.PLAYOFF_MULT, abs=1e-9)


# ===========================================================
# THE SUMMER RESET
# ===========================================================

def test_teams_move_back_towards_average_between_seasons():
    """
    Last year's champions do not start the new season as last year's champions.

    Rosters change, so 30% of every team's edge is handed back at the reset.
    """
    strong = elo.TeamState(1700, season=20242025)
    elo.start_new_season(strong, 20252026)
    assert strong.elo == pytest.approx(1505 + (1700 - 1505) * 0.7, abs=1e-6)

    weak = elo.TeamState(1300, season=20242025)
    elo.start_new_season(weak, 20252026)
    assert 1300 < weak.elo < elo.MEAN_ELO


def test_the_reset_only_happens_once_per_season():
    state = elo.TeamState(1700, season=20242025)
    elo.start_new_season(state, 20252026)
    after_first = state.elo
    elo.start_new_season(state, 20252026)
    assert state.elo == after_first


# ===========================================================
# SAVING AND RELOADING
# ===========================================================

def test_a_team_survives_a_round_trip_through_json():
    """
    The ratings live in team_state.json between nightly runs, so a field lost
    in serialisation would silently reset part of the model every day.
    """
    original = elo.TeamState(1612.5, decay_gd=1.25, decay_win=0.64,
                             season=20252026, features={"a": 1.0})
    restored = elo.TeamState.from_dict(original.to_dict())

    assert restored.elo == pytest.approx(original.elo, abs=1e-3)
    assert restored.decay_win == pytest.approx(original.decay_win, abs=1e-5)
    assert restored.season == original.season
    assert restored.features == original.features


def test_matchup_features_are_the_ones_the_model_was_trained_on(): 
    features = elo.matchup_features(elo.TeamState(1600), elo.TeamState(1500))
    for name in ("home_elo_pre", "away_elo_pre", "elo_diff", "elo_prob_home",
                 "decay_goal_diff_diff", "decay_win_rate_diff"):
        assert name in features
    assert features["elo_diff"] == 100
