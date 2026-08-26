from __future__ import annotations

from datetime import date
from typing import Any

from tqdm import tqdm

from config import PROCESSED_DIR, RAW_DIR
from src.nhl_client import NHLClient
from src.utils import default_text, monthly_snapshot_dates, save_csv


def fetch_standings_snapshot(client: NHLClient, snapshot_date: date, season: int) -> list[dict[str, Any]]:
    payload = client.get_web(
        f"standings/{snapshot_date.isoformat()}",
        RAW_DIR / "standings" / str(season) / f"{snapshot_date.isoformat()}.json",
        optional=True,
    )
    rows = []
    for row in (payload or {}).get("standings", []):
        flattened = dict(row)
        flattened["snapshot_date"] = snapshot_date.isoformat()
        flattened["season"] = row.get("seasonId") or season
        flattened["team"] = default_text(row.get("teamAbbrev"))
        flattened["team_name"] = default_text(row.get("teamName"))
        rows.append(flattened)
    return rows


def fetch_standings(client: NHLClient, seasons: list[int], stop_date: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for season in seasons:
        for snapshot_date in tqdm(monthly_snapshot_dates(season, stop_date), desc=f"Standings {season}"):
            rows.extend(fetch_standings_snapshot(client, snapshot_date, season))
    save_csv(PROCESSED_DIR / "standings.csv", rows)
    return rows
