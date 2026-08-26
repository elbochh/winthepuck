from __future__ import annotations

from config import PROCESSED_DIR, RAW_DIR
from src.nhl_client import NHLClient
from src.utils import save_csv


def fetch_team_stats(client: NHLClient, seasons: list[int]) -> list[dict]:
    rows: list[dict] = []
    for season in seasons:
        payload = client.get_stats_paginated(
            "team/summary",
            RAW_DIR / "stats" / str(season) / "team_summary.json",
            base_params={"cayenneExp": f"seasonId={season}"},
        )
        rows.extend(payload.get("data", []))
    save_csv(PROCESSED_DIR / "team_season_stats.csv", rows)
    return rows
