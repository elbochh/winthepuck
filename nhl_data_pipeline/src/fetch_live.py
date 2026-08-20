from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from config import PROCESSED_DIR, RAW_DIR
from src.fetch_schedule import UPCOMING_COLUMNS, flatten_game
from src.nhl_client import NHLClient


LIVE_GAME_STATES = {"PRE", "LIVE", "CRIT"}
LIVE_OR_UPCOMING_GAME_STATES = LIVE_GAME_STATES | {"FUT"}


def fetch_live_data(client: NHLClient, target_date: date) -> pd.DataFrame:
    """Fetch no-key public NHL live/schedule feeds plus gamecenter artifacts.

    A timestamped snapshot is used so repeated live runs preserve raw API state
    instead of replacing yesterday's view with today's.
    """

    snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = RAW_DIR / "live" / target_date.isoformat() / snapshot_id

    payloads = [
        client.get_web_snapshot("score/now", snapshot_dir / "score_now.json", optional=True),
        client.get_web_snapshot(f"score/{target_date.isoformat()}", snapshot_dir / "score_date.json", optional=True),
        client.get_web_snapshot(f"schedule/{target_date.isoformat()}", snapshot_dir / "schedule_date.json", optional=True),
        client.get_web_snapshot("scoreboard/now", snapshot_dir / "scoreboard_now.json", optional=True),
    ]

    games = _collect_games(payloads)
    for game in games.values():
        if game.get("gameState") in LIVE_OR_UPCOMING_GAME_STATES:
            _fetch_live_gamecenter(client, game, snapshot_dir)

    rows = [flatten_game(game) for game in games.values()]
    df = pd.DataFrame(rows)
    for column in UPCOMING_COLUMNS:
        if column not in df.columns:
            df[column] = None
    if not df.empty:
        df = df.sort_values(["game_date", "start_time_utc", "game_id"])
    df = df[UPCOMING_COLUMNS]
    df.to_csv(PROCESSED_DIR / "live_games.csv", index=False)
    return df


def latest_live_snapshot_dir() -> Path | None:
    live_root = RAW_DIR / "live"
    if not live_root.exists():
        return None
    snapshots = [path for path in live_root.glob("*/*") if path.is_dir()]
    return sorted(snapshots)[-1] if snapshots else None


def _fetch_live_gamecenter(client: NHLClient, game: dict[str, Any], snapshot_dir: Path) -> None:
    game_id = game.get("id")
    if game_id is None:
        return
    game_dir = snapshot_dir / "games" / str(game_id)
    client.get_web_snapshot(f"gamecenter/{game_id}/landing", game_dir / "landing.json", optional=True)
    client.get_web_snapshot(f"gamecenter/{game_id}/boxscore", game_dir / "boxscore.json", optional=True)
    client.get_web_snapshot(f"gamecenter/{game_id}/play-by-play", game_dir / "play_by_play.json", optional=True)
    client.get_web_snapshot(f"gamecenter/{game_id}/right-rail", game_dir / "right_rail.json", optional=True)


def _collect_games(payloads: list[Any | None]) -> dict[int, dict[str, Any]]:
    games_by_id: dict[int, dict[str, Any]] = {}
    for payload in payloads:
        for game in _games_from_payload(payload):
            game_id = game.get("id")
            if game_id is not None:
                games_by_id[int(game_id)] = game
    return games_by_id


def _games_from_payload(payload: Any | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("games"), list):
        return list(payload["games"])

    games: list[dict[str, Any]] = []
    for day in payload.get("gameWeek", []) or []:
        games.extend(day.get("games", []) or [])
    for day in payload.get("gamesByDate", []) or []:
        games.extend(day.get("games", []) or [])
    return games
