"""Recent-form features, and the rule that keeps them honest.

Every number the model sees about a team has to be computable from games that
had already finished when the puck dropped. The single most damaging bug
possible in this file would be a feature that quietly includes the game it is
being used to predict - the model would look brilliant in testing and fall
apart live. That is what most of these tests are guarding.
"""
from __future__ import annotations

from datetime import date

import pytest

from form_book import FormBook, last_five_form


def game(game_id, day, home, away, home_score, away_score,
         season=20252026, period="REG"):
    return {
        "game_id": game_id, "season": season, "game_date": day,
        "home_team": home, "away_team": away,
        "home_score": home_score, "away_score": away_score,
        "last_period_type": period, "finished": True,
        "game_type": 2,
    }


@pytest.fixture
def book():
    """Five days of results: TOR win three of four, MTL win one."""
    book = FormBook()
    book.add(game(1, "2025-10-01", "TOR", "MTL", 4, 1))
    book.add(game(2, "2025-10-03", "MTL", "TOR", 2, 5))
    book.add(game(3, "2025-10-05", "TOR", "BOS", 1, 3))
    book.add(game(4, "2025-10-07", "BOS", "TOR", 0, 2))
    book.sort()
    return book


# ===========================================================
# THE RULE THAT MATTERS MOST
# ===========================================================

def test_a_team_has_no_form_before_its_first_game(book):
    assert book.team_features("TOR", date(2025, 9, 30), 20252026) == {}


def test_form_never_includes_the_game_being_predicted(book):
    """
    Asking for a team's form on a day it played must not count that day's game.

    This is the leak that makes a model look far better than it is, so it is
    checked directly: the record on the 7th must match the record on the 6th.
    """
    day_before = book.team_features("TOR", date(2025, 10, 6), 20252026)
    match_day = book.team_features("TOR", date(2025, 10, 7), 20252026)
    assert day_before["last_5_win_pct"] == match_day["last_5_win_pct"]


def test_form_grows_as_games_are_played(book):
    after_one = book.team_features("TOR", date(2025, 10, 2), 20252026)
    after_all = book.team_features("TOR", date(2025, 10, 8), 20252026)
    assert after_one["last_5_win_pct"] == 1.0        # one game, one win
    assert after_all["last_5_win_pct"] == 0.75       # three of four


# ===========================================================
# THE INDIVIDUAL FEATURES
# ===========================================================

def test_goals_are_counted_from_each_teams_own_side(book):
    toronto = book.team_features("TOR", date(2025, 10, 8), 20252026)
    montreal = book.team_features("MTL", date(2025, 10, 8), 20252026)
    # TOR scored 4, 5, 1, 2 = 3.0 a game. MTL conceded 4 and 5.
    assert toronto["last_5_goals_for_avg"] == pytest.approx(3.0)
    assert montreal["last_5_goals_against_avg"] == pytest.approx(4.5)


def test_rest_days_and_back_to_backs(book):
    """A team playing on consecutive nights is measurably worse, so the model
    needs to know."""
    features = book.team_features("TOR", date(2025, 10, 8), 20252026)
    assert features["rest_days"] == 1
    assert features["back_to_back"] == 1.0

    rested = book.team_features("TOR", date(2025, 10, 14), 20252026)
    assert rested["back_to_back"] == 0.0
    assert rested["rest_days"] == 7


def test_rest_days_are_capped_so_the_summer_does_not_dominate(book):
    """
    Between seasons the gap is months. Left uncapped, that one number would
    dwarf every other input on opening night.
    """
    assert book.team_features("TOR", date(2026, 5, 1), 20252026)["rest_days"] == 14


def test_home_and_road_records_are_kept_apart(book):
    toronto = book.team_features("TOR", date(2025, 10, 8), 20252026)
    assert toronto["home_win_pct_before_game"] == 0.5      # won 1 of 2 at home
    assert toronto["road_win_pct_before_game"] == 1.0      # won both away


def test_games_in_the_last_week_are_counted(book):
    features = book.team_features("TOR", date(2025, 10, 8), 20252026)
    assert features["games_last_7_days"] == 4
    assert features["games_last_3_days"] == 2


def test_a_new_season_starts_the_season_records_over(book):
    """
    Season records restart in October, and the model was trained on them being
    absent. Inventing a number would be worse than leaving it out.
    """
    features = book.team_features("TOR", date(2026, 10, 8), 20262027)
    assert "season_points_pct_before_game" not in features
    # Career form still carries over.
    assert "last_5_win_pct" in features


# ===========================================================
# HEAD TO HEAD
# ===========================================================

def test_head_to_head_reads_from_the_home_teams_point_of_view(book):
    """
    TOR beat MTL twice - once at home, once away. Asked about TOR at home,
    that has to read as two wins; asked the other way round, two losses.
    """
    from_toronto = book.head_to_head("TOR", "MTL", date(2025, 10, 8))
    assert from_toronto["h2h_home_team_win_pct_last_5"] == 1.0
    assert from_toronto["h2h_games_last_365_days"] == 2

    from_montreal = book.head_to_head("MTL", "TOR", date(2025, 10, 8))
    assert from_montreal["h2h_home_team_win_pct_last_5"] == 0.0


def test_teams_that_have_not_met_report_no_history(book):
    assert book.head_to_head("TOR", "VAN", date(2025, 10, 8)) == {
        "h2h_games_last_365_days": 0.0}


# ===========================================================
# THE W / L / O PILLS ON THE WEBSITE
# ===========================================================

def test_an_overtime_loss_is_shown_differently_from_a_regulation_one():
    """
    Losing in overtime still earns a point in the NHL, so the site marks it
    O rather than L.
    """
    book = FormBook()
    book.add(game(1, "2025-10-01", "TOR", "MTL", 4, 1))
    book.add(game(2, "2025-10-03", "TOR", "BOS", 2, 3, period="OT"))
    book.add(game(3, "2025-10-05", "TOR", "OTT", 1, 4))
    book.sort()

    assert last_five_form(book, 20252026)["TOR"] == ["W", "O", "L"]


def test_only_the_last_five_games_are_shown():
    book = FormBook()
    for index in range(8):
        book.add(game(index, f"2025-10-{index + 1:02d}", "TOR", "MTL", 3, 1))
    book.sort()
    assert len(last_five_form(book, 20252026)["TOR"]) == 5


def test_unfinished_games_are_ignored_entirely():
    book = FormBook()
    scheduled = game(1, "2025-10-01", "TOR", "MTL", None, None)
    scheduled["finished"] = False
    book.add(scheduled)
    assert book.team_features("TOR", date(2025, 10, 8), 20252026) == {}
