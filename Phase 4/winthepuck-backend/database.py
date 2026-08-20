"""
WinThePuck - database helper functions
Phase 4: Back End Development

Every part of the website talks to the SQLite database through the
small functions in this file, so we only write the connection code once.
"""

import os
import sqlite3

# The database file sits in the same folder as this file.
BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(BASE_FOLDER, "winthepuck.db")
SCHEMA_FILE = os.path.join(BASE_FOLDER, "schema.sql")


def get_connection():
    """Open a connection to the SQLite database."""
    connection = sqlite3.connect(DATABASE_FILE)
    # This lets us read a column by its name, for example row["username"],
    # instead of by a number like row[3]. It makes the code easier to read.
    connection.row_factory = sqlite3.Row
    # Turn on foreign keys so SQLite checks that the ids we save really exist.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def query_all(sql, values=()):
    """Run a SELECT and return every row as a list."""
    connection = get_connection()
    rows = connection.execute(sql, values).fetchall()
    connection.close()
    return rows


def query_one(sql, values=()):
    """Run a SELECT and return only the first row (or None if there is none)."""
    connection = get_connection()
    row = connection.execute(sql, values).fetchone()
    connection.close()
    return row


def run_command(sql, values=()):
    """Run an INSERT, UPDATE or DELETE and return the new row id."""
    connection = get_connection()
    cursor = connection.execute(sql, values)
    connection.commit()
    new_id = cursor.lastrowid
    connection.close()
    return new_id


def build_database():
    """Create all of the empty tables by running schema.sql."""
    connection = get_connection()
    with open(SCHEMA_FILE, "r", encoding="utf-8") as schema:
        connection.executescript(schema.read())
    connection.commit()
    connection.close()
    print("Tables created in " + DATABASE_FILE)


def database_exists():
    """True when the database file has already been created."""
    return os.path.exists(DATABASE_FILE)
