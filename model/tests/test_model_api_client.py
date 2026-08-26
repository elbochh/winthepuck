"""The NHL API client, and the outage that used to take the whole job down.

On 20 August 2026 the nightly run failed. The predictions had already been
calculated; what broke was a call for the team stats that decorate the matchup
page, which answered 503 for about a minute. A cosmetic endpoint took a day of
predictions with it.

These tests describe how it behaves now: retry properly, and treat "nice to
have" data as nice to have.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

import nhl_api


class FakeServer:
    """Answers a scripted sequence of responses, one per call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, request, timeout=None):
        self.calls += 1
        answer = self.responses.pop(0) if self.responses else self.responses
        if isinstance(answer, Exception):
            raise answer
        return _Body(answer)


class _Body(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def http_error(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("http://x", code, "boom", headers, None)


@pytest.fixture(autouse=True)
def no_real_sleeping(monkeypatch):
    """Backoff waits are real seconds; the tests should not spend them."""
    monkeypatch.setattr(nhl_api.time, "sleep", lambda _seconds: None)


# ===========================================================
# RETRYING
# ===========================================================

def test_a_good_answer_is_returned_straight_away(monkeypatch):
    server = FakeServer({"games": [1, 2]})
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen", server)
    assert nhl_api.get_json("http://x") == {"games": [1, 2]}
    assert server.calls == 1


def test_a_temporary_failure_is_retried_and_then_succeeds(monkeypatch):
    """This is the exact shape of the outage that broke the job."""
    server = FakeServer(http_error(503), http_error(503), {"ok": True})
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen", server)
    assert nhl_api.get_json("http://x") == {"ok": True}
    assert server.calls == 3


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_the_codes_worth_retrying_are_retried(monkeypatch, code):
    server = FakeServer(http_error(code), {"ok": True})
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen", server)
    assert nhl_api.get_json("http://x") == {"ok": True}


@pytest.mark.parametrize("code", [400, 401, 403])
def test_a_permanent_failure_gives_up_immediately(monkeypatch, code):
    """
    A bad request will fail identically five times. Retrying it just makes the
    job take a minute longer to report the same problem.
    """
    server = FakeServer(*[http_error(code)] * 6)
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen", server)
    with pytest.raises(RuntimeError):
        nhl_api.get_json("http://x")
    assert server.calls == 1


def test_a_missing_page_is_empty_rather_than_an_error(monkeypatch):
    """404 from this API means "no games", which is a normal answer."""
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen",
                        FakeServer(http_error(404)))
    assert nhl_api.get_json("http://x") == {}


def test_a_dropped_connection_is_retried(monkeypatch):
    server = FakeServer(TimeoutError("connection reset"), {"ok": True})
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen", server)
    assert nhl_api.get_json("http://x") == {"ok": True}


def test_it_eventually_gives_up_and_says_which_address_failed(monkeypatch):
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen",
                        FakeServer(*[http_error(503)] * 10))
    with pytest.raises(RuntimeError, match="standings"):
        nhl_api.get_json("http://api.nhle.com/standings")


# ===========================================================
# BACKOFF
# ===========================================================

def test_the_wait_grows_each_time():
    """
    Hammering a struggling server at a fixed rate is what keeps it down. The
    delay doubles, so it gets room to recover.
    """
    waits = [nhl_api._sleep_for(attempt) for attempt in range(4)]
    assert waits[0] < waits[-1]
    assert all(w > 0 for w in waits)


def test_the_wait_is_capped():
    assert nhl_api._sleep_for(50) <= nhl_api.BACKOFF_CAP


def test_two_clients_do_not_retry_in_lockstep():
    """
    The random fraction matters more than it looks. Without it, everything
    that failed together retries together and the server gets a fresh spike
    every round.
    """
    waits = {nhl_api._sleep_for(3) for _ in range(30)}
    assert len(waits) > 20


def test_the_server_is_believed_when_it_says_how_long_to_wait():
    assert nhl_api._sleep_for(0, retry_after="7") == 7.0
    # ...but not beyond our own ceiling, and not if it is nonsense.
    assert nhl_api._sleep_for(0, retry_after="99999") == nhl_api.BACKOFF_CAP
    assert nhl_api._sleep_for(0, retry_after="soon") > 0


# ===========================================================
# DEGRADING INSTEAD OF DYING
# ===========================================================

def test_optional_data_returns_nothing_rather_than_failing(monkeypatch, capsys):
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen",
                        FakeServer(*[http_error(503)] * 10))
    assert nhl_api.get_json_optional("http://x", "team stats") is None
    assert "carrying on without it" in capsys.readouterr().out.lower()


def test_team_stats_no_longer_bring_the_job_down(monkeypatch):
    """The regression test for the 20 August failure."""
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen",
                        FakeServer(*[http_error(503)] * 20))
    assert nhl_api.club_stats(20252026) == {}


def test_the_standings_no_longer_bring_the_job_down(monkeypatch):
    monkeypatch.setattr(nhl_api.urllib.request, "urlopen",
                        FakeServer(*[http_error(503)] * 20))
    assert nhl_api.standings() == []


# ===========================================================
# READING A GAME
# ===========================================================

RAW_GAME = {
    "id": 2025020001, "season": 20252026, "gameType": 2,
    "gameDate": "2025-10-07", "startTimeUTC": "2025-10-07T23:00:00Z",
    "gameState": "OFF",
    "venue": {"default": "Amerant Bank Arena"},
    "homeTeam": {"abbrev": "FLA", "score": 3, "logo": "fla.svg",
                 "commonName": {"default": "Panthers"},
                 "placeName": {"default": "Florida"}},
    "awayTeam": {"abbrev": "CHI", "score": 2, "logo": "chi.svg",
                 "commonName": {"default": "Blackhawks"},
                 "placeName": {"default": "Chicago"}},
    "gameOutcome": {"lastPeriodType": "REG"},
}


def test_a_finished_game_keeps_its_score():
    flat = nhl_api.flatten_game(RAW_GAME)
    assert flat["finished"] is True
    assert (flat["home_score"], flat["away_score"]) == (3, 2)
    assert flat["home_team"] == "FLA"


def test_a_scheduled_game_has_no_score_yet():
    """
    A future game sometimes arrives carrying a score of 0-0. Trusting it would
    record every upcoming game as a scoreless draw.
    """
    scheduled = dict(RAW_GAME, gameState="FUT")
    scheduled["homeTeam"] = dict(RAW_GAME["homeTeam"], score=0)
    scheduled["awayTeam"] = dict(RAW_GAME["awayTeam"], score=0)

    flat = nhl_api.flatten_game(scheduled)
    assert flat["finished"] is False
    assert flat["home_score"] is None
    assert flat["away_score"] is None


def test_dates_are_read_from_either_format():
    from datetime import date
    assert nhl_api.parse_date("2025-10-07") == date(2025, 10, 7)
    assert nhl_api.parse_date("2025-10-07T23:00:00Z") == date(2025, 10, 7)
