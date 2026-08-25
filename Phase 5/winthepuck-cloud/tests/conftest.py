"""Shared fixtures for the website tests.

Every test gets its own throwaway database built from the real seed files in
`data/`, so the tests exercise the same code path that runs on Azure the very
first time the site starts: schema, seeding, scoring, all of it.

The important trick is the environment variable. `config.py` decides where the
database lives when it is imported, so WINTHEPUCK_DATA_DIR has to be set
*before* anything imports it - which is why it happens at the top of this file
rather than inside a fixture.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.mkdtemp(prefix="winthepuck-tests-")
os.environ["WINTHEPUCK_DATA_DIR"] = _TEMP_DIR
os.environ["SECRET_KEY"] = "test-key-not-a-secret"
os.environ["REFRESH_TOKEN"] = "test-refresh-token"
# Generous limits so ordinary tests are never throttled; the throttling tests
# build their own limiter instead of relying on these.
os.environ["LOGIN_ATTEMPTS"] = "1000"

import app as flask_app  # noqa: E402
import database  # noqa: E402


@pytest.fixture(scope="session")
def app():
    flask_app.app.config.update(TESTING=True)
    return flask_app.app


@pytest.fixture
def app_context(app):
    """
    One application context per test, shared by every fixture that needs it.

    Flask keeps the database handle on `g`, which belongs to whichever context
    is on top. If the client and the raw connection each pushed their own, a
    test would be looking at two different handles and the contexts would
    unwind out of order on the way out.
    """
    with app.app_context():
        yield


@pytest.fixture
def client(app, app_context):
    """A browser-like client with its own cookie jar."""
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def connection(app_context):
    """The same database handle the request being tested is using."""
    return database.get_connection()


@pytest.fixture
def csrf(client):
    """
    Reads the CSRF token out of the session, the way a real form carries it.

    Every POST has to send back the token the server put in the session, or
    the tests would only ever be exercising the rejection path.

    This hands back a function rather than a string on purpose: signing out
    clears the session, so a token captured once at the start of a test goes
    stale the moment `/logout` is called. Asking for it at the point of use
    always gets the live one.
    """
    def token() -> str:
        with client.session_transaction() as session:
            return session.setdefault("csrf_token", "test-csrf-token")
    return token
