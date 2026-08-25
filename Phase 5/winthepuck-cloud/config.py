"""Settings for the website.

Anything secret (the session key, the refresh token) is read from an
environment variable so it never has to be written in the code or pushed to
GitHub. On Azure we set these under "Environment variables" in the App
Service, and on our own laptops the safe fallbacks below are used instead.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Azure App Service gives every site a folder called /home that survives
# restarts and redeploys. That is where the database has to live, otherwise
# every new deployment would wipe the members and their comments.
ON_AZURE = Path("/home/site/wwwroot").exists()
DATA_DIR = Path(os.environ.get("WINTHEPUCK_DATA_DIR",
                               "/home/data" if ON_AZURE else HERE / "instance"))

DATABASE_FILE = DATA_DIR / "winthepuck.db"
SCHEMA_FILE = HERE / "schema.sql"
SEED_DIR = HERE / "data"

# Flask uses this to sign the cookie that keeps members logged in.
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# The daily prediction job sends new predictions to /api/admin/refresh and
# proves who it is with this token. Without one set, that route is switched off.
REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN", "")

# The password on the read-only demo account, so a marker can sign in and try
# the members-only features without registering.
DEMO_USERNAME = "demo"
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "puck1234")

# How many finished games to show on one page of the results table.
RESULTS_PAGE_SIZE = 25

# Points for the leaderboard.
POINTS_FOR_CORRECT = 100
POINTS_FOR_WRONG = 10

# ---- how hard somebody is allowed to hammer the site ----
# Six tries a minute is plenty for a person who has forgotten their password,
# and useless for a script working through a word list.
LOGIN_ATTEMPTS = int(os.environ.get("LOGIN_ATTEMPTS", 6))
LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", 60))

# The daily job posts once a day. Ten an hour leaves room to re-run it by hand
# after a failure without ever getting near the limit.
REFRESH_ATTEMPTS = int(os.environ.get("REFRESH_ATTEMPTS", 10))
REFRESH_WINDOW_SECONDS = int(os.environ.get("REFRESH_WINDOW_SECONDS", 3600))
