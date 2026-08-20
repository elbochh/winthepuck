from __future__ import annotations

from typing import Any

from tqdm import tqdm

from config import PROCESSED_DIR, RAW_DIR
from src.nhl_client import NHLClient
from src.utils import default_text, save_csv


def fetch_roster(client: NHLClient, team_abbrev: str) -> dict[str, Any]:
    return client.get_web(
        f"roster/{team_abbrev}/current",
        RAW_DIR / "rosters" / f"{team_abbrev}.json",
        optional=True,
    ) or {}


def fetch_rosters(client: NHLClient, team_abbrevs: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for team in tqdm(sorted(set(team_abbrevs)), desc="Rosters"):
        payload = fetch_roster(client, team)
        for group in ("forwards", "defensemen", "goalies"):
            for player in payload.get(group, []):
                rows.append(
                    {
                        "team": team,
                        "group": group,
                        "player_id": player.get("id"),
                        "player_name": f"{default_text(player.get('firstName')) or ''} {default_text(player.get('lastName')) or ''}".strip(),
                        "position": player.get("positionCode"),
                        "sweater_number": player.get("sweaterNumber"),
                        "shoots_catches": player.get("shootsCatches"),
                        "birth_date": player.get("birthDate"),
                        "height_inches": player.get("heightInInches"),
                        "weight_pounds": player.get("weightInPounds"),
                    }
                )
    save_csv(PROCESSED_DIR / "rosters.csv", rows)
    return rows
