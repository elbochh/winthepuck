"""Registering, signing in, picking a team and posting a message.

This is the part of the site where a bug costs somebody their account or lets
one member act as another, so the tests here are mostly about what should
*not* be allowed.
"""
from __future__ import annotations

import secrets


def register(client, csrf, username, password="puck1234", confirm=None):
    return client.post("/register", data={
        "username": username,
        "password": password,
        "confirm": password if confirm is None else confirm,
        "csrf_token": csrf(),
    }, follow_redirects=True)


def new_name() -> str:
    return "user_" + secrets.token_hex(4)


# ===========================================================
# REGISTRATION
# ===========================================================

def test_a_new_member_can_register_and_is_signed_in(client, csrf):
    name = new_name()
    response = register(client, csrf, name)
    assert response.status_code == 200
    assert b"Welcome to WinThePuck" in response.data
    with client.session_transaction() as session:
        assert session["username"] == name


def test_the_same_username_cannot_be_taken_twice(client, csrf):
    name = new_name()
    register(client, csrf, name)
    client.get("/logout")
    assert b"already taken" in register(client, csrf, name).data


def test_registration_rejects_bad_input(client, csrf):
    assert b"3 and 20 characters" in register(client, csrf, "ab").data
    assert b"letters, numbers and underscores" in register(client, csrf, "bad name!").data
    assert b"at least 6 characters" in register(client, csrf, new_name(), password="123").data
    assert b"do not match" in register(client, csrf, new_name(), confirm="different1").data


def test_the_password_is_never_stored_as_typed(client, connection, csrf):
    name = new_name()
    register(client, csrf, name)
    stored = connection.execute(
        "SELECT password_hash FROM users WHERE username = ?", (name,)).fetchone()
    assert "puck1234" not in stored["password_hash"]
    assert stored["password_hash"].startswith(("pbkdf2:", "scrypt:"))


# ===========================================================
# SIGNING IN
# ===========================================================

def test_sign_in_and_out(client, csrf):
    name = new_name()
    register(client, csrf, name)
    client.get("/logout")

    response = client.post("/login", data={
        "username": name, "password": "puck1234",
        "csrf_token": csrf()}, follow_redirects=True)
    assert b"Signed in as" in response.data

    client.get("/logout")
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_a_wrong_password_says_nothing_useful(client, csrf):
    name = new_name()
    register(client, csrf, name)
    client.get("/logout")

    response = client.post("/login", data={
        "username": name, "password": "wrong-password",
        "csrf_token": csrf()}, follow_redirects=True)
    # Deliberately the same message as an unknown username, so the form cannot
    # be used to find out which accounts exist.
    assert b"Wrong username or password" in response.data


def test_a_strategy_account_cannot_be_signed_into(client, csrf):
    """
    The five leaderboard strategies are back-tests, not people.

    They exist so the leaderboard has something real in it on day one. Letting
    somebody sign in as ModelFollower would let them rewrite that history.
    """
    response = client.post("/login", data={
        "username": "ModelFollower", "password": "puck1234",
        "csrf_token": csrf()}, follow_redirects=True)
    assert b"Wrong username or password" in response.data


# ===========================================================
# PICKS
# ===========================================================

def test_a_pick_needs_an_account(client, csrf):
    games = client.get("/api/games").get_json()
    response = client.post(f"/predict/{games[0]['id']}", data={
        "team_id": games[0]["home"]["id"],
        "csrf_token": csrf()}, follow_redirects=True)
    assert b"sign in to save a pick" in response.data


def test_a_member_can_pick_and_change_their_mind(client, connection, csrf):
    register(client, csrf, new_name())
    game = client.get("/api/games").get_json()[0]

    for team in (game["home"], game["away"]):
        response = client.post(f"/predict/{game['id']}", data={
            "team_id": team["id"], "csrf_token": csrf()},
            follow_redirects=True)
        assert b"Pick saved" in response.data

    # Changing a pick updates the one row rather than adding a second.
    with client.session_transaction() as session:
        user_id = session["user_id"]
    rows = connection.execute(
        "SELECT picked_team_id FROM predictions WHERE user_id = ? AND game_id = ?",
        (user_id, game["id"])).fetchall()
    assert len(rows) == 1
    assert rows[0]["picked_team_id"] == game["away"]["id"]


def test_you_cannot_pick_a_team_that_is_not_playing(client, csrf):
    register(client, csrf, new_name())
    games = client.get("/api/games").get_json()
    game = games[0]
    outsider = next(g["home"]["id"] for g in games
                    if g["home"]["id"] not in (game["home"]["id"], game["away"]["id"]))

    response = client.post(f"/predict/{game['id']}", data={
        "team_id": outsider, "csrf_token": csrf()}, follow_redirects=True)
    assert b"not playing in this game" in response.data


def test_you_cannot_pick_a_game_that_has_already_been_played(client, connection, csrf):
    register(client, csrf, new_name())
    finished = connection.execute(
        "SELECT id, home_team_id FROM games WHERE status = 'final' LIMIT 1").fetchone()

    response = client.post(f"/predict/{finished['id']}", data={
        "team_id": finished["home_team_id"], "csrf_token": csrf()},
        follow_redirects=True)
    assert b"picks are closed" in response.data


# ===========================================================
# COMMENTS
# ===========================================================

def test_posting_and_liking_a_message(client, csrf):
    register(client, csrf, new_name())
    game = client.get("/api/games").get_json()[0]

    response = client.post(f"/discussion/{game['id']}/post", data={
        "body": "Goalie has been unbeatable lately.", "pick": "home",
        "csrf_token": csrf()}, follow_redirects=True)
    assert b"Your message was posted" in response.data
    assert b"Goalie has been unbeatable" in response.data


def test_an_empty_or_enormous_message_is_refused(client, csrf):
    register(client, csrf, new_name())
    game = client.get("/api/games").get_json()[0]

    empty = client.post(f"/discussion/{game['id']}/post", data={
        "body": "   ", "pick": "home", "csrf_token": csrf()},
        follow_redirects=True)
    assert b"message was empty" in empty.data

    huge = client.post(f"/discussion/{game['id']}/post", data={
        "body": "x" * 501, "pick": "home", "csrf_token": csrf()},
        follow_redirects=True)
    assert b"shorter than 500" in huge.data


def test_a_message_is_escaped_rather_than_run(client, csrf):
    """A comment containing HTML must come back as text, not as markup."""
    register(client, csrf, new_name())
    game = client.get("/api/games").get_json()[0]

    client.post(f"/discussion/{game['id']}/post", data={
        "body": "<script>alert('xss')</script>", "pick": "home",
        "csrf_token": csrf()}, follow_redirects=True)

    page = client.get(f"/discussion/{game['id']}").data
    assert b"<script>alert" not in page
    assert b"&lt;script&gt;" in page
