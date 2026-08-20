from __future__ import annotations

from config import PROCESSED_DIR, RAW_DIR
from src.nhl_client import NHLClient
from src.utils import save_csv


def fetch_goalie_stats(client: NHLClient, seasons: list[int]) -> list[dict]:
    rows: list[dict] = []
    for season in seasons:
        payload = client.get_stats_paginated(
            "goalie/summary",
            RAW_DIR / "stats" / str(season) / "goalie_summary.json",
            base_params={"cayenneExp": f"seasonId={season}"},
        )
        rows.extend(payload.get("data", []))
    save_csv(PROCESSED_DIR / "goalie_season_stats.csv", rows)
    return rows
