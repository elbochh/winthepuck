from __future__ import annotations

from typing import Any

import pandas as pd

from config import DEFAULT_START_SEASON, PROCESSED_DIR, RAW_DIR
from src.nhl_client import NHLClient
from src.utils import save_csv


def fetch_seasons(client: NHLClient) -> list[int]:
    payload = client.get_web("season", RAW_DIR / "seasons" / "seasons.json")
    seasons = sorted(int(season) for season in (payload or []))
    save_csv(PROCESSED_DIR / "seasons.csv", [{"season": season} for season in seasons], ["season"])
    return seasons


def resolve_season_range(client: NHLClient, start_season: int | None, end_season: int | None) -> list[int]:
    seasons = fetch_seasons(client)
    start = start_season or DEFAULT_START_SEASON
    end = end_season or max(seasons)
    return [season for season in seasons if start <= season <= end]


def fetch_team_metadata(client: NHLClient) -> list[dict[str, Any]]:
    payload = client.get_stats("team", RAW_DIR / "teams" / "teams.json")
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    save_csv(PROCESSED_DIR / "teams.csv", rows)
    return rows


def team_id_to_abbrev(client: NHLClient) -> dict[int, str]:
    rows = fetch_team_metadata(client)
    return {
        int(row["id"]): row.get("triCode") or row.get("rawTricode")
        for row in rows
        if row.get("id") is not None and (row.get("triCode") or row.get("rawTricode"))
    }


def fetch_active_team_abbrevs(client: NHLClient, season: int) -> list[str]:
    mapping = team_id_to_abbrev(client)
    payload = client.get_stats_paginated(
        "team/summary",
        RAW_DIR / "stats" / str(season) / "team_summary_all.json",
        base_params={"cayenneExp": f"seasonId={season}"},
    )
    team_ids = sorted({int(row["teamId"]) for row in payload.get("data", []) if row.get("teamId") is not None})
    abbrevs = sorted({mapping[team_id] for team_id in team_ids if team_id in mapping})
    if not abbrevs:
        teams = pd.DataFrame(fetch_team_metadata(client))
        if "triCode" in teams.columns:
            abbrevs = sorted(teams["triCode"].dropna().unique().tolist())
    return abbrevs
