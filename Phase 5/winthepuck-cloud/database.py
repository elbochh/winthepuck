"""Everything that talks to the SQLite database.

Keeping the connection code in one file means the rest of the website can just
call `query_all(...)` or `run_command(...)` and not worry about opening and
closing connections.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from flask import g

import config


def get_connection() -> sqlite3.Connection:
    """
    Open the database, or reuse the connection this request already has.

    Flask gives every request a little box called `g`. Storing the connection
    there means one page never opens the database twenty times over.
    """
    connection = getattr(g, "_database", None)
    if connection is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(config.DATABASE_FILE, timeout=15)
        # Lets us read a column by name, e.g. row["username"], instead of row[3].
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        # WAL lets somebody read the site while the refresh job is writing.
        connection.execute("PRAGMA journal_mode = WAL")
        g._database = connection
    return connection


def close_connection(_exception: BaseException | None = None) -> None:
    """Called by Flask at the end of every request."""
    connection = getattr(g, "_database", None)
    if connection is not None:
        connection.close()
        g._database = None


def query_all(sql: str, values: tuple = ()) -> list[sqlite3.Row]:
    """Run a SELECT and give back every row."""
    return get_connection().execute(sql, values).fetchall()


def query_one(sql: str, values: tuple = ()) -> sqlite3.Row | None:
    """Run a SELECT and give back the first row, or None."""
    return get_connection().execute(sql, values).fetchone()


def query_value(sql: str, values: tuple = (), default: Any = None) -> Any:
    """Run a SELECT that returns a single number, such as a COUNT."""
    row = query_one(sql, values)
    if row is None or row[0] is None:
        return default
    return row[0]


def run_command(sql: str, values: tuple = ()) -> int:
    """Run an INSERT, UPDATE or DELETE and give back the new row id."""
    connection = get_connection()
    cursor = connection.execute(sql, values)
    connection.commit()
    return cursor.lastrowid


def build_tables() -> None:
    """Create every empty table by running schema.sql."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(config.DATABASE_FILE)
    connection.executescript(config.SCHEMA_FILE.read_text(encoding="utf-8"))
    connection.commit()
    connection.close()


def tables_exist() -> bool:
    """True once the database has been built."""
    if not config.DATABASE_FILE.exists():
        return False
    connection = sqlite3.connect(config.DATABASE_FILE)
    try:
        found = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='teams'"
        ).fetchone()
        return found is not None
    finally:
        connection.close()


def get_meta(key: str, default: str = "") -> str:
    row = query_one("SELECT value FROM site_meta WHERE key = ?", (key,))
    return row["value"] if row else default


def set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT INTO site_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
