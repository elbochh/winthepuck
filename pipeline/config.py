from __future__ import annotations

from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOG_DIR = PROJECT_ROOT / "logs"

WEB_API_BASE = "https://api-web.nhle.com/v1"
STATS_API_BASE = "https://api.nhle.com/stats/rest/en"

# Earliest season verified to support the current full feature set across
# schedules, Gamecenter boxscores/play-by-play, shift charts, and season stats.
DEFAULT_START_SEASON = 20102011
REQUEST_TIMEOUT = 30
MAX_RETRIES = 4
BACKOFF_SECONDS = 1.0
REQUEST_DELAY_SECONDS = 0.2
STATS_PAGE_SIZE = 100

COMPLETED_GAME_STATES = {"OFF", "FINAL"}
REGULAR_SEASON_GAME_TYPE = 2


def current_date() -> date:
    return date.today()


def ensure_directories() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
