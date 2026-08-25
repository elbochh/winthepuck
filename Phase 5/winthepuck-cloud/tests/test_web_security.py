"""The defences: CSRF, the refresh token, throttling and response headers.

Each of these is a rule the site relies on but that nothing else would notice
if it quietly stopped working, which is exactly the kind of thing worth
pinning down in a test.
"""
from __future__ import annotations

import json

import pytest

import config
import security

# ===========================================================
# CROSS-SITE REQUEST FORGERY
# ===========================================================

def test_a_form_without_a_token_is_refused(client):
    """
    The point of the token is that another website cannot guess it.

    Without this check, a page somebody else controls could quietly make a
    logged-in visitor's browser post a comment or change a pick.
    """
    game = client.get("/api/games").get_json()[0]
    response = client.post(f"/predict/{game['id']}", data={"team_id": game["home"]["id"]})
    assert response.status_code == 400


def test_a_form_with_somebody_elses_token_is_refused(client, csrf):
    game = client.get("/api/games").get_json()[0]
    csrf()          # give this visitor a real token first
    response = client.post(f"/predict/{game['id']}", data={
        "team_id": game["home"]["id"], "csrf_token": "not-the-right-token"})
    assert response.status_code == 400


# ===========================================================
# THE REFRESH ENDPOINT
# ===========================================================

REFRESH_PAYLOAD = {
    "generatedAt": "2026-08-25T12:00:00+00:00",
    "season": 20262027,
    "teams": [],
    "upcoming": [],
    "finished": [],
}


def post_refresh(client, token, payload=None):
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post("/api/admin/refresh",
                       data=json.dumps(REFRESH_PAYLOAD if payload is None else payload),
                       headers=headers)


def test_refresh_needs_the_token(client):
    assert post_refresh(client, None).status_code == 401
    assert post_refresh(client, "wrong-token").status_code == 401


def test_refresh_accepts_the_right_token(client):
    response = post_refresh(client, config.REFRESH_TOKEN)
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_refresh_rejects_something_that_is_not_a_payload(client):
    response = post_refresh(client, config.REFRESH_TOKEN, payload={"nonsense": True})
    assert response.status_code == 400


def test_refresh_updates_the_scores_of_finished_games(client, connection):
    """A real delivery: a game that was upcoming comes back with a result."""
    game = connection.execute(
        "SELECT games.nhl_game_id, h.abbr AS home, a.abbr AS away "
        "FROM games JOIN teams h ON h.id = games.home_team_id "
        "JOIN teams a ON a.id = games.away_team_id "
        "WHERE games.status = 'upcoming' LIMIT 1").fetchone()

    payload = dict(REFRESH_PAYLOAD, finished=[{
        "gameId": game["nhl_game_id"], "gameDate": "2026-09-29",
        "home": game["home"], "away": game["away"],
        "homeScore": 4, "awayScore": 2, "winner": game["home"],
        "overtime": False,
    }])
    body = post_refresh(client, config.REFRESH_TOKEN, payload).get_json()
    assert body["results"] == 1

    updated = connection.execute(
        "SELECT status, home_score, away_score FROM games WHERE nhl_game_id = ?",
        (game["nhl_game_id"],)).fetchone()
    assert updated["status"] == "final"
    assert (updated["home_score"], updated["away_score"]) == (4, 2)


# ===========================================================
# RESPONSE HEADERS
# ===========================================================

@pytest.mark.parametrize("header,expected", [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
])
def test_protective_headers_are_present(client, header, expected):
    assert client.get("/").headers[header] == expected


def test_the_content_security_policy_locks_scripts_to_our_own_origin(client):
    policy = client.get("/").headers["Content-Security-Policy"]
    assert "script-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    # Team crests genuinely do come from the NHL, so that one host is allowed.
    assert "https://assets.nhle.com" in policy


def test_scripts_may_never_be_inline():
    """
    The half of the policy that actually stops cross-site scripting.

    Styles are allowed inline (see below); scripts must never be. If these two
    are ever confused, the policy stops being worth having.
    """
    policy = security.CONTENT_SECURITY_POLICY
    script_rule = next(r for r in policy.split("; ") if r.startswith("script-src"))
    assert "unsafe-inline" not in script_rule
    assert "unsafe-eval" not in script_rule


def test_styles_are_allowed_inline_because_the_interface_needs_them(client):
    """
    A regression test for a policy that was briefly too strict.

    Club colours and probability-bar widths come out of the database as style
    attributes, because the value differs for every row. Refusing them made
    every bar on the site collapse to zero width - and nothing errored,
    because the HTML was perfectly correct and the browser simply declined to
    apply it. Server-side tests cannot see that, so the rule is pinned here.
    """
    policy = client.get("/").headers["Content-Security-Policy"]
    style_rule = next(r for r in policy.split("; ") if r.startswith("style-src"))
    assert "unsafe-inline" in style_rule

    # ...and the markup really does rely on it.
    page = client.get("/games").data
    assert b'style="width:' in page or b"style=\"--c:" in page


def test_hsts_is_only_promised_over_https():
    """
    Promising HSTS on plain http is meaningless, so it is tied to being deployed.
    """
    class FakeResponse:
        def __init__(self):
            self.headers = {}

    assert "Strict-Transport-Security" not in security.apply_headers(
        FakeResponse(), https=False).headers
    assert "Strict-Transport-Security" in security.apply_headers(
        FakeResponse(), https=True).headers


# ===========================================================
# RATE LIMITING
# ===========================================================

def test_the_limiter_allows_then_refuses():
    limiter = security.RateLimiter(limit=3, window_seconds=60)
    assert [limiter.allow("1.2.3.4", now=0) for _ in range(3)] == [True, True, True]
    assert limiter.allow("1.2.3.4", now=0) is False


def test_the_limiter_forgets_old_attempts():
    """Attempts age out, so somebody is not locked out for ever."""
    limiter = security.RateLimiter(limit=2, window_seconds=60)
    limiter.allow("1.2.3.4", now=0)
    limiter.allow("1.2.3.4", now=1)
    assert limiter.allow("1.2.3.4", now=2) is False
    assert limiter.allow("1.2.3.4", now=100) is True


def test_one_visitor_cannot_lock_out_another():
    limiter = security.RateLimiter(limit=1, window_seconds=60)
    limiter.allow("1.1.1.1", now=0)
    assert limiter.allow("1.1.1.1", now=0) is False
    assert limiter.allow("2.2.2.2", now=0) is True


def test_a_successful_sign_in_clears_the_record():
    limiter = security.RateLimiter(limit=2, window_seconds=60)
    limiter.allow("1.2.3.4", now=0)
    limiter.reset("1.2.3.4")
    assert limiter.allow("1.2.3.4", now=0) is True


def test_retry_after_counts_down():
    limiter = security.RateLimiter(limit=1, window_seconds=60)
    limiter.allow("1.2.3.4", now=0)
    assert limiter.retry_after("1.2.3.4", now=0) == 61
    assert limiter.retry_after("1.2.3.4", now=30) == 31
    assert limiter.retry_after("nobody-seen-before") == 0


def test_the_real_address_is_read_from_the_proxy_header():
    """
    Azure puts a load balancer in front, so remote_addr is the balancer.

    Without this, every visitor would look like the same caller and one person
    typing their password wrong would throttle everybody.
    """
    class FakeRequest:
        def __init__(self, headers, remote):
            self.headers = headers
            self.remote_addr = remote

    assert security.client_address(
        FakeRequest({"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}, "10.0.0.1")
    ) == "203.0.113.7"
    assert security.client_address(FakeRequest({}, "198.51.100.4")) == "198.51.100.4"
    assert security.client_address(FakeRequest({}, None)) == "unknown"
