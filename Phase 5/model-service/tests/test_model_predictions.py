"""The serving path: building a feature row, and running the real model on it.

The trained model expects 127 numbers in a fixed order. Nothing enforces that
at run time - hand it the columns in the wrong order and it will cheerfully
return a probability that means nothing at all. These tests load the actual
shipped model and check the row we build for it lines up.
"""
from __future__ import annotations

from datetime import date

import pytest

import elo
import refresh_predictions as refresh
from form_book import FormBook

# ===========================================================
# ODDS
# ===========================================================

@pytest.mark.parametrize("probability,expected", [
    (0.5, -100),
    (0.75, -300),
    (0.25, 300),
    (0.9, -900),
])
def test_fair_odds_carry_no_house_edge(probability, expected):
    """
    These are the odds implied by the probability exactly.

    A bookmaker would shade them in their own favour; we do not, which is why
    the site says these are not a betting recommendation.
    """
    assert refresh.fair_odds(probability) == expected


def test_odds_are_clamped_at_the_extremes():
    assert refresh.fair_odds(0.0) == 4900
    assert refresh.fair_odds(1.0) == -4900


def test_the_two_sides_of_a_game_price_opposite_ways():
    for probability in (0.55, 0.7, 0.85):
        assert refresh.fair_odds(probability) < 0
        assert refresh.fair_odds(1 - probability) > 0


# ===========================================================
# WHICH SEASON A DATE BELONGS TO
# ===========================================================

@pytest.mark.parametrize("day,expected", [
    (date(2026, 10, 15), 20262027),   # October is the start of a new season
    (date(2027, 3, 1), 20262027),     # March still belongs to it
    (date(2026, 6, 14), 20252026),    # a June final is last season
    (date(2026, 8, 1), 20262027),     # August is when the new one is counted
])
def test_a_date_maps_to_the_right_season(day, expected):
    assert refresh.season_id(day) == expected


# ===========================================================
# THE FEATURE ROW
# ===========================================================

@pytest.fixture(scope="module")
def bundle():
    """The model that is actually deployed, loaded from serving/."""
    return refresh.load_bundle()


@pytest.fixture(scope="module")
def state():
    return refresh.load_state()


def build_a_row(feature_cols, saved_state):
    """
    A feature row built the same way the nightly job builds one.

    The team ratings come from the real serving/team_state.json rather than
    from made-up numbers, because the box-score half of the row lives in there
    and a hand-written stub would not exercise it.
    """
    states = {abbr: elo.TeamState.from_dict(data)
              for abbr, data in saved_state["teams"].items()}

    book = FormBook()
    fixtures = [
        ("TOR", "MTL", 4, 1), ("MTL", "TOR", 2, 5), ("TOR", "BOS", 1, 3),
        ("BOS", "TOR", 0, 2), ("TOR", "OTT", 3, 2), ("MTL", "OTT", 2, 1),
        ("MTL", "BOS", 3, 4), ("MTL", "TOR", 1, 2),
    ]
    for index, (home, away, home_score, away_score) in enumerate(fixtures):
        book.add({"game_id": index, "season": 20252026,
                  "game_date": f"2025-10-{index + 1:02d}",
                  "home_team": home, "away_team": away,
                  "home_score": home_score, "away_score": away_score,
                  "last_period_type": "REG", "finished": True, "game_type": 2})
    book.sort()
    game_day = date(2025, 10, 20)

    return refresh.build_row(
        states["TOR"], states["MTL"],
        book.team_features("TOR", game_day, 20252026),
        book.team_features("MTL", game_day, 20252026),
        book.head_to_head("TOR", "MTL", game_day),
        feature_cols, season_game_index=40)


def test_the_shipped_model_is_what_we_think_it_is(bundle):
    models, feature_cols = bundle
    assert set(models) == {"hgb", "logit", "catboost"}
    assert len(feature_cols) == 127
    # No duplicated column names - a duplicate would silently shift every
    # column after it out of position.
    assert len(set(feature_cols)) == len(feature_cols)


def test_the_row_we_build_covers_the_columns_the_model_expects(bundle, state):
    _, feature_cols = bundle
    row = build_a_row(feature_cols, state)
    missing = [column for column in feature_cols if column not in row]

    # Every one of the 127 columns the model was trained on has to be present.
    # `season_points_pct_diff` used to be absent on every single prediction the
    # site made, because the pipeline names that column's two halves with a
    # `_before_game` suffix that the difference-building loop did not know
    # about. Nothing failed - the logistic model simply imputed the training
    # average - which is exactly why it went unnoticed and why it is asserted
    # exactly here rather than as a percentage.
    assert missing == []


def test_the_difference_columns_are_home_minus_away(bundle, state):
    """
    About half the inputs are stored a second time as a difference. Getting
    the sign backwards here would invert the model's view of every matchup.
    """
    _, feature_cols = bundle
    row = build_a_row(feature_cols, state)

    for column in feature_cols:
        if not column.endswith("_diff"):
            continue
        base = column[: -len("_diff")]
        home, away = f"home_{base}", f"away_{base}"
        if home in row and away in row and column in row:
            assert row[column] == pytest.approx(row[home] - row[away], abs=1e-9)


def test_a_regular_season_game_carries_empty_playoff_columns(bundle, state):
    _, feature_cols = bundle
    row = build_a_row(feature_cols, state)
    assert row["is_playoff"] == 0.0
    for column, value in refresh.REGULAR_SEASON_PLAYOFF_COLUMNS.items():
        assert row[column] == value


def test_the_real_model_returns_a_usable_probability(bundle, state):
    """
    End to end: the shipped model, a real feature row, a real probability.

    If the column order ever drifted out of step with training, this is where
    it would show up.
    """
    models, feature_cols = bundle
    row = build_a_row(feature_cols, state)
    probabilities = refresh.predict(models, feature_cols, [row])

    assert len(probabilities) == 1
    probability = float(probabilities[0])
    assert 0.0 < probability < 1.0


def test_a_stronger_team_at_home_is_given_a_better_chance(bundle, state):
    """
    The direction check: swap the two clubs and the answer has to move.

    A fixed threshold would only say something about whichever two teams
    happened to be picked. Comparing the league's best side against its worst,
    both ways round, tests the thing that actually matters - that the ratings
    reach the model the right way up. A column order that had drifted out of
    step with training would sail past every other test in this file and fail
    here.
    """
    models, feature_cols = bundle
    states = {abbr: elo.TeamState.from_dict(data)
              for abbr, data in state["teams"].items()}
    ranked = sorted(states.items(), key=lambda pair: pair[1].elo)
    weakest, strongest = ranked[0][1], ranked[-1][1]
    assert strongest.elo - weakest.elo > 50, "need a real gap to test against"

    def probability(home, away):
        row = refresh.build_row(home, away, {}, {},
                                {"h2h_games_last_365_days": 0.0},
                                feature_cols, season_game_index=40)
        return float(refresh.predict(models, feature_cols, [row])[0])

    strong_at_home = probability(strongest, weakest)
    weak_at_home = probability(weakest, strongest)

    assert strong_at_home > 0.5 > weak_at_home


def test_the_ensemble_sits_between_its_members(bundle, state):
    """The ensemble is a mean, so it can never be more extreme than all three."""
    models, feature_cols = bundle
    row = build_a_row(feature_cols, state)

    ensemble = float(refresh.predict(models, feature_cols, [row])[0])
    singles = [float(refresh.predict({name: model}, feature_cols, [row])[0])
               for name, model in models.items()]

    assert min(singles) <= ensemble <= max(singles)


def test_several_games_are_scored_in_one_pass(bundle, state):
    models, feature_cols = bundle
    rows = [build_a_row(feature_cols, state) for _ in range(3)]
    assert len(refresh.predict(models, feature_cols, rows)) == 3


# ===========================================================
# THE SAVED RATINGS
# ===========================================================

def test_the_saved_state_covers_the_whole_league(state):
    assert state["season"] > 0
    assert len(state["teams"]) >= 32
    for abbr in ("TOR", "EDM", "FLA", "VGK"):
        assert abbr in state["teams"]


def test_saved_ratings_are_in_a_believable_range(state):
    """
    Elo is zero-sum around 1505. A team outside 1200-1800 means something has
    gone wrong in the replay, not that they are unusually good.
    """
    ratings = [team["elo"] for team in state["teams"].values()]
    assert all(1200 < rating < 1800 for rating in ratings)
    average = sum(ratings) / len(ratings)
    assert 1450 < average < 1560


def test_the_season_record_gap_is_actually_calculated(bundle, state):
    """
    The regression test for the column that was silently missing.

    It is the difference between the two clubs' season points percentages, so
    a team on a better run than its opponent must produce a positive number.
    """
    _, feature_cols = bundle
    row = build_a_row(feature_cols, state)

    assert "season_points_pct_diff" in row
    assert row["season_points_pct_diff"] == pytest.approx(
        row["home_season_points_pct_before_game"]
        - row["away_season_points_pct_before_game"], abs=1e-9)
