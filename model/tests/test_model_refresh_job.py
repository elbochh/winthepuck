"""The daily job's own logic, with the network held still.

`replay` is the quiet heart of the whole thing. Every night it walks the games
that have finished since the last run and moves the Elo ratings forward. Get it
wrong - apply a game twice, skip one, or misread the cut-off date - and every
prediction the site makes afterwards is built on corrupted ratings, with
nothing anywhere raising an error.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

import elo
import nhl_api
import refresh_predictions as refresh


def finished(game_id, day, home, away, home_score, away_score,
             season=20252026, game_type=2):
    return {
        "game_id": game_id, "season": season, "game_type": game_type,
        "game_date": day, "home_team": home, "away_team": away,
        "home_score": home_score, "away_score": away_score,
        "last_period_type": "REG", "finished": True,
        "start_time_utc": f"{day}T23:00:00Z", "venue": "Arena",
        "home_logo": "", "away_logo": "",
        "home_name": home, "away_name": away,
        "home_city": home, "away_city": away,
    }


def scheduled(game_id, day, home, away, season=20252026):
    game = finished(game_id, day, home, away, None, None, season)
    game["finished"] = False
    return game


@pytest.fixture
def states():
    return {abbr: elo.TeamState(1500, season=20252026)
            for abbr in ("TOR", "MTL", "BOS", "OTT")}


# ===========================================================
# CATCHING UP ON RESULTS
# ===========================================================

def test_only_games_since_the_last_run_are_applied(states):
    """
    The cut-off is what stops the same game being counted twice.

    Every run downloads the whole season, including games already applied on
    previous nights. Re-applying them would compound a team's rating a little
    further every single day.
    """
    games = [
        finished(1, "2025-10-01", "TOR", "MTL", 5, 1),   # before the cut-off
        finished(2, "2025-10-05", "TOR", "BOS", 4, 0),   # on the cut-off
        finished(3, "2025-10-09", "TOR", "OTT", 3, 1),   # after it - counts
    ]
    applied = refresh.replay(states, games, known_until=date(2025, 10, 5))
    assert applied == 1
    assert states["TOR"].elo > 1500
    assert states["MTL"].elo == 1500      # untouched, already applied earlier


def test_running_twice_changes_nothing_the_second_time(states):
    """The job must be safe to re-run after a failure."""
    games = [finished(1, "2025-10-09", "TOR", "MTL", 4, 2)]
    refresh.replay(states, games, known_until=date(2025, 10, 5))
    after_first = states["TOR"].elo

    # A re-run is given the new cut-off, exactly as the saved state records it.
    refresh.replay(states, games, known_until=date(2025, 10, 9))
    assert states["TOR"].elo == after_first


def test_unplayed_games_are_ignored(states):
    games = [scheduled(1, "2025-12-01", "TOR", "MTL")]
    assert refresh.replay(states, games, known_until=date(2025, 10, 1)) == 0
    assert states["TOR"].elo == 1500


def test_a_club_we_have_never_seen_starts_at_the_league_average(states):
    games = [finished(1, "2025-10-09", "TOR", "UTA", 3, 2)]
    refresh.replay(states, games, known_until=date(2025, 10, 1))
    assert "UTA" in states
    assert states["UTA"].elo < elo.MEAN_ELO      # it just lost


def test_ratings_stay_zero_sum_across_a_whole_replay(states):
    """
    Every game moves one rating up and the other down by the same amount, so
    the league total cannot drift.
    """
    before = sum(state.elo for state in states.values())
    games = [
        finished(1, "2025-10-09", "TOR", "MTL", 4, 1),
        finished(2, "2025-10-11", "BOS", "OTT", 2, 3),
        finished(3, "2025-10-13", "MTL", "BOS", 5, 2),
    ]
    refresh.replay(states, games, known_until=date(2025, 10, 1))
    assert sum(state.elo for state in states.values()) == pytest.approx(before, abs=1e-9)


def test_a_new_season_resets_before_the_first_game_is_applied(states):
    """
    The summer reset has to land before the new season's games, not after.

    Applied the wrong way round, the first result of the year would be wiped
    out by the reset that should have preceded it.
    """
    states["TOR"].elo = 1700
    games = [finished(1, "2026-10-09", "TOR", "MTL", 3, 1, season=20262027)]
    refresh.replay(states, games, known_until=date(2026, 6, 1))

    # 1700 reverts to 1505 + 195 * 0.7 = 1641.5, then the win is added.
    assert 1641 < states["TOR"].elo < 1650


def test_preparing_for_a_season_reverts_every_club(states):
    for state in states.values():
        state.elo = 1700
    refresh.prepare_for_season(states, 20262027)

    for state in states.values():
        assert state.elo < 1700
        assert state.season == 20262027


# ===========================================================
# THE LEAGUE TABLE
# ===========================================================

def test_the_table_is_empty_rather_than_wrong_when_the_standings_are_down(
        monkeypatch, states, capsys):
    """
    The 20 August failure, from the job's side.

    With no standings the job sends no teams, and the website keeps the table
    it already has. The predictions in the same payload are untouched.
    """
    monkeypatch.setattr(nhl_api, "standings", lambda _on_date=None: [])
    monkeypatch.setattr(nhl_api, "club_stats", lambda _season: {})
    monkeypatch.setattr(refresh, "standings_end", lambda _season: date(2026, 4, 1))

    from form_book import FormBook
    table = refresh.team_table([], FormBook(), 20252026, states)

    assert table == []
    assert "predictions only" in capsys.readouterr().out


def test_the_table_is_built_from_the_standings_when_they_are_available(
        monkeypatch, states):
    monkeypatch.setattr(refresh, "standings_end", lambda _season: date(2026, 4, 1))
    monkeypatch.setattr(nhl_api, "standings", lambda _on_date=None: [{
        "teamAbbrev": {"default": "TOR"}, "teamName": {"default": "Toronto Maple Leafs"},
        "wins": 45, "losses": 30, "otLosses": 7, "points": 97,
        "pointPctg": 0.591, "gamesPlayed": 82,
        "streakCode": "W", "streakCount": 3,
    }])
    monkeypatch.setattr(nhl_api, "club_stats", lambda _season: {
        "TOR": {"goalsFor": 3.2, "goalsAgainst": 2.9}})

    from form_book import FormBook
    games = [finished(1, "2025-10-09", "TOR", "MTL", 4, 1)] * 1
    book = FormBook()
    for game in games:
        book.add(game)
    book.sort()

    table = refresh.team_table(games, book, 20252026, states)

    assert len(table) == 1
    assert table[0]["abbr"] == "TOR"
    assert table[0]["record"] == "45-30-7"
    assert table[0]["points"] == 97
    assert table[0]["streak"] == "W3"
    assert table[0]["stats"]["goalsFor"] == 3.2
    assert table[0]["elo"] == pytest.approx(states["TOR"].elo, abs=0.1)


def test_an_almost_empty_new_season_keeps_showing_last_years_records(
        monkeypatch, states, capsys):
    """
    In October the new table is nearly blank, and a site full of 0-0-0 records
    looks broken. Last season's table is shown until enough games are played.
    """
    seen = {}
    monkeypatch.setattr(refresh, "standings_end", lambda season: date(2026, 4, 1))
    monkeypatch.setattr(nhl_api, "standings", lambda _on_date=None: [])
    monkeypatch.setattr(nhl_api, "club_stats",
                        lambda season: seen.setdefault("season", season) and {})

    from form_book import FormBook
    refresh.team_table([], FormBook(), 20262027, states)

    assert seen["season"] == 20252026          # last season, not the new one
    assert "showing 20252026 records" in capsys.readouterr().out


# ===========================================================
# SENDING IT TO THE WEBSITE
# ===========================================================

def test_the_payload_is_posted_with_the_token(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def read(self):
            return b'{"status":"ok"}'

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.data.decode())
        return FakeResponse()

    monkeypatch.setattr(refresh.urllib.request, "urlopen", fake_urlopen)
    refresh.post_payload("https://winthepuck.azurewebsites.net/", "secret-token",
                         {"teams": [], "upcoming": []})

    assert captured["url"].endswith("/api/admin/refresh")
    assert captured["method"] == "POST"
    assert captured["auth"] == "Bearer secret-token"
    assert captured["body"] == {"teams": [], "upcoming": []}


def test_a_trailing_slash_does_not_produce_a_double_slash(monkeypatch):
    urls = []

    class FakeResponse:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(refresh.urllib.request, "urlopen",
                        lambda request, timeout=None: (
                            urls.append(request.full_url), FakeResponse())[1])

    for base in ("https://site.example", "https://site.example/"):
        refresh.post_payload(base, "token", {})

    assert urls == ["https://site.example/api/admin/refresh"] * 2
