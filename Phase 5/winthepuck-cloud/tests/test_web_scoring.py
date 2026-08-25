"""Leaderboard points, streaks, and the odds shown next to each prediction."""
from __future__ import annotations

import pytest

import monitoring
import nhl_data
import scoring

# ===========================================================
# STREAKS
# ===========================================================

def test_a_streak_stops_at_the_first_miss():
    """The list arrives newest first, so counting stops at the first 0."""
    assert scoring.count_streak([1, 1, 1, 0, 1, 1]) == 3
    assert scoring.count_streak([0, 1, 1, 1]) == 0
    assert scoring.count_streak([1, 1, 1]) == 3
    assert scoring.count_streak([]) == 0


# ===========================================================
# POINTS
# ===========================================================

def test_settling_a_pick_pays_out_and_only_once(client, connection):
    """
    Scoring runs on every leaderboard view, so it has to be safe to repeat.

    If it were not, a member's points would climb every time somebody opened
    the page.
    """
    game = connection.execute(
        "SELECT id, home_team_id, winner_team_id FROM games "
        "WHERE status = 'final' AND winner_team_id IS NOT NULL LIMIT 1").fetchone()
    user_id = nhl_data.create_account(
        connection, "settle_test", "irrelevant-password", 12, "member", "")

    connection.execute(
        "INSERT INTO predictions (user_id, game_id, picked_team_id, made_on) "
        "VALUES (?, ?, ?, '2026-01-01') "
        "ON CONFLICT (user_id, game_id) DO NOTHING",
        (user_id, game["id"], game["winner_team_id"]))
    connection.commit()

    assert scoring.settle_predictions(connection) >= 1
    # Nothing is left waiting, so a second run has no work to do.
    assert scoring.settle_predictions(connection) == 0

    row = connection.execute(
        "SELECT is_correct, points FROM predictions WHERE user_id = ? AND game_id = ?",
        (user_id, game["id"])).fetchone()
    assert row["is_correct"] == 1
    assert row["points"] == 100


def test_a_wrong_pick_still_earns_something(client, connection):
    """Turning up is worth 10 points, so playing every night is never a penalty."""
    game = connection.execute(
        "SELECT id, home_team_id, away_team_id, winner_team_id FROM games "
        "WHERE status = 'final' AND winner_team_id IS NOT NULL LIMIT 1").fetchone()
    loser = (game["away_team_id"] if game["winner_team_id"] == game["home_team_id"]
             else game["home_team_id"])
    user_id = nhl_data.create_account(
        connection, "wrong_pick_test", "irrelevant-password", 12, "member", "")

    connection.execute(
        "INSERT INTO predictions (user_id, game_id, picked_team_id, made_on) "
        "VALUES (?, ?, ?, '2026-01-01') "
        "ON CONFLICT (user_id, game_id) DO NOTHING",
        (user_id, game["id"], loser))
    connection.commit()
    scoring.settle_predictions(connection)

    row = connection.execute(
        "SELECT is_correct, points FROM predictions WHERE user_id = ? AND game_id = ?",
        (user_id, game["id"])).fetchone()
    assert row["is_correct"] == 0
    assert row["points"] == 10


def test_an_unplayed_game_is_left_alone(client, connection):
    upcoming = connection.execute(
        "SELECT id, home_team_id FROM games WHERE status = 'upcoming' LIMIT 1").fetchone()
    user_id = nhl_data.create_account(
        connection, "pending_test", "irrelevant-password", 12, "member", "")

    connection.execute(
        "INSERT INTO predictions (user_id, game_id, picked_team_id, made_on) "
        "VALUES (?, ?, ?, '2026-01-01') "
        "ON CONFLICT (user_id, game_id) DO NOTHING",
        (user_id, upcoming["id"], upcoming["home_team_id"]))
    connection.commit()
    scoring.settle_predictions(connection)

    row = connection.execute(
        "SELECT is_correct FROM predictions WHERE user_id = ? AND game_id = ?",
        (user_id, upcoming["id"])).fetchone()
    assert row["is_correct"] is None


# ===========================================================
# ODDS
# ===========================================================

@pytest.mark.parametrize("probability,expected", [
    (0.50, -100),      # an even game is priced level both ways
    (0.75, -300),
    (0.25, 300),
])
def test_fair_odds_match_the_probability(probability, expected):
    assert nhl_data.american_odds(probability) == expected


def test_odds_stay_sane_at_the_extremes():
    """Clamped, so a 0% prediction cannot divide by zero."""
    assert nhl_data.american_odds(0.0) == 4900
    assert nhl_data.american_odds(1.0) == -4900


def test_a_favourite_is_always_priced_negative():
    for probability in (0.51, 0.6, 0.8, 0.97):
        assert nhl_data.american_odds(probability) < 0
        assert nhl_data.american_odds(1 - probability) > 0


# ===========================================================
# THE MONITORING REPORT
# ===========================================================

def test_the_monitoring_report_has_every_section_the_page_needs(client):
    report = monitoring.build_report()
    for key in ("baselineSeason", "reference", "live", "comparison", "drift"):
        assert key in report


def test_the_baseline_is_measured_on_the_walk_forward_season(client):
    report = monitoring.build_report()
    assert report["reference"]["enough"] is True
    assert report["reference"]["games"] > 1000
    # The published figure is around 55% for this season; anything wildly
    # outside that means the wrong games are being counted.
    assert 45 < report["reference"]["accuracy"] < 70


def test_live_and_baseline_games_never_overlap(client):
    """
    The baseline is the season the published track record came from. Live
    games are the ones this deployment predicted itself. Counting a game in
    both would let the model mark its own homework.
    """
    report = monitoring.build_report()
    baseline = report["baselineSeason"]
    before = monitoring.graded_games("AND season <= ?", (baseline,))
    after = monitoring.graded_games("AND season > ?", (baseline,))
    assert not ({r["season"] for r in before} & {r["season"] for r in after})
