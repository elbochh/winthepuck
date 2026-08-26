"""Every page of the website answers, and answers with the right thing on it.

These are the tests that would have caught a broken template or a query that
stopped returning rows - the sort of failure that only shows up when somebody
actually opens the page.
"""
from __future__ import annotations

import pytest

PUBLIC_PAGES = [
    "/", "/games", "/matchups", "/results", "/monitoring",
    "/leaderboard", "/discussion", "/login", "/register",
]

JSON_ROUTES = [
    "/api/games", "/api/model", "/api/leaderboard", "/api/monitoring", "/healthz",
]


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_page_opens(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b"<html" in response.data


@pytest.mark.parametrize("path", JSON_ROUTES)
def test_json_route_returns_json(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.is_json


def test_unknown_page_is_a_friendly_404(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert b"could not find" in response.data.lower()


def test_health_check_reports_a_full_database(client):
    body = client.get("/healthz").get_json()
    assert body["status"] == "ok"
    # The seed loads all 32 clubs and a full season of finished games. If the
    # first-run build silently half-failed, this is where it shows.
    assert body["teams"] == 32
    assert body["games"] > 1000


def test_results_page_paginates(client):
    first = client.get("/results?page=1")
    assert first.status_code == 200
    # Asking for a page past the end should clamp rather than break.
    assert client.get("/results?page=99999").status_code == 200
    assert client.get("/results?page=-4").status_code == 200


@pytest.mark.parametrize("only", ["all", "correct", "missed", "playoffs"])
def test_results_filters(client, only):
    assert client.get(f"/results?filter={only}").status_code == 200


def test_matchup_page_for_a_specific_game(client):
    games = client.get("/api/games").get_json()
    assert games, "the seed should leave some upcoming games to compare"
    response = client.get(f"/matchups/{games[0]['id']}")
    assert response.status_code == 200
    assert games[0]["home"]["abbr"].encode() in response.data


def test_matchup_page_rejects_a_game_that_does_not_exist(client):
    assert client.get("/matchups/99999999").status_code == 404


def test_live_replay_advances_one_event_at_a_time(client):
    first = client.get("/api/live").get_json()
    second = client.get("/api/live").get_json()
    assert second["total_events"] == first["total_events"]
    # Each call shows one more event than the last, which is what makes the
    # chart on the home page move.
    assert len(second["events"]) == len(first["events"]) + 1


def test_every_game_carries_a_probability_and_matching_odds(client):
    for game in client.get("/api/games").get_json():
        assert 0 <= game["home_win_prob"] <= 100
        assert game["home_win_prob"] + game["away_win_prob"] == pytest.approx(100, abs=0.2)
        assert game["confidence"] >= 50
        # A favourite is priced as a negative American line, the underdog positive.
        favourite_odds = (game["home_odds"] if game["home_win_prob"] >= 50
                          else game["away_odds"])
        assert favourite_odds.startswith("-")


def test_model_scorecard_lists_the_ensemble_first(client):
    body = client.get("/api/model").get_json()
    assert body["models"][0]["model"] == "WinThePuck Ensemble"
    assert float(body["overallAccuracy"]) > 50
