from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from config import PROCESSED_DIR, RAW_DIR
from src.utils import read_json, save_csv


PLAY_BY_PLAY_COLUMNS = [
    "game_id",
    "season",
    "game_type",
    "game_date",
    "event_id",
    "sort_order",
    "period",
    "period_type",
    "period_time",
    "time_remaining",
    "seconds_elapsed",
    "period_seconds_elapsed",
    "event_type",
    "team",
    "team_id",
    "team_side",
    "player_1",
    "player_2",
    "winning_player_id",
    "losing_player_id",
    "shooting_player_id",
    "blocking_player_id",
    "hitting_player_id",
    "hittee_player_id",
    "scoring_player_id",
    "assist1_player_id",
    "assist2_player_id",
    "goalie_in_net_id",
    "committed_by_player_id",
    "drawn_by_player_id",
    "served_by_player_id",
    "x_coord",
    "y_coord",
    "zone",
    "strength",
    "situation_code",
    "home_team_defending_side",
    "shot_type",
    "penalty_type",
    "penalty_minutes",
    "reason",
    "home_score",
    "away_score",
    "home_sog",
    "away_sog",
    "result",
    "description",
    "raw_details_json",
]


def flatten_play_by_play(games_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for game in games_df.itertuples(index=False):
        path = RAW_DIR / "games" / str(game.season) / str(game.game_id) / "play_by_play.json"
        if path.exists():
            rows.extend(_flatten_game_pbp(path))
    return save_csv(PROCESSED_DIR / "play_by_play.csv", rows, PLAY_BY_PLAY_COLUMNS)


def _flatten_game_pbp(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    home = payload.get("homeTeam") or {}
    away = payload.get("awayTeam") or {}
    team_id_map = {
        home.get("id"): home.get("abbrev"),
        away.get("id"): away.get("abbrev"),
    }
    team_side_map = {
        home.get("id"): "home",
        away.get("id"): "away",
    }
    rows = []
    for play in payload.get("plays", []):
        details = play.get("details") or {}
        players = _player_ids(details)
        period = (play.get("periodDescriptor") or {}).get("number")
        period_time = play.get("timeInPeriod")
        event_team_id = details.get("eventOwnerTeamId")
        rows.append(
            {
                "game_id": payload.get("id"),
                "season": payload.get("season"),
                "game_type": payload.get("gameType"),
                "game_date": payload.get("gameDate"),
                "event_id": play.get("eventId"),
                "sort_order": play.get("sortOrder"),
                "period": period,
                "period_type": (play.get("periodDescriptor") or {}).get("periodType"),
                "period_time": period_time,
                "time_remaining": play.get("timeRemaining"),
                "seconds_elapsed": _game_seconds(period, period_time),
                "period_seconds_elapsed": _clock_to_seconds(period_time),
                "event_type": play.get("typeDescKey"),
                "team": team_id_map.get(event_team_id),
                "team_id": event_team_id,
                "team_side": team_side_map.get(event_team_id),
                "player_1": players[0] if len(players) > 0 else None,
                "player_2": players[1] if len(players) > 1 else None,
                "winning_player_id": details.get("winningPlayerId"),
                "losing_player_id": details.get("losingPlayerId"),
                "shooting_player_id": details.get("shootingPlayerId"),
                "blocking_player_id": details.get("blockingPlayerId"),
                "hitting_player_id": details.get("hittingPlayerId"),
                "hittee_player_id": details.get("hitteePlayerId"),
                "scoring_player_id": details.get("scoringPlayerId"),
                "assist1_player_id": details.get("assist1PlayerId"),
                "assist2_player_id": details.get("assist2PlayerId"),
                "goalie_in_net_id": details.get("goalieInNetId"),
                "committed_by_player_id": details.get("committedByPlayerId"),
                "drawn_by_player_id": details.get("drawnByPlayerId"),
                "served_by_player_id": details.get("servedByPlayerId"),
                "x_coord": details.get("xCoord"),
                "y_coord": details.get("yCoord"),
                "zone": details.get("zoneCode"),
                "strength": details.get("strength") or play.get("situationCode"),
                "situation_code": play.get("situationCode"),
                "home_team_defending_side": play.get("homeTeamDefendingSide"),
                "shot_type": details.get("shotType"),
                "penalty_type": details.get("typeCode"),
                "penalty_minutes": details.get("duration"),
                "reason": details.get("reason") or details.get("secondaryReason") or details.get("descKey"),
                "home_score": details.get("homeScore"),
                "away_score": details.get("awayScore"),
                "home_sog": details.get("homeSOG"),
                "away_sog": details.get("awaySOG"),
                "result": play.get("typeDescKey"),
                "description": _description(play, details),
                "raw_details_json": json.dumps(details, sort_keys=True) if details else None,
            }
        )
    return rows


def _player_ids(details: dict[str, Any]) -> list[Any]:
    ids: list[Any] = []
    for key, value in details.items():
        if key.endswith("PlayerId") and value is not None:
            ids.append(value)
    for key in ("committedByPlayer", "drawnBy"):
        value = details.get(key)
        if isinstance(value, dict) and value.get("playerId") is not None:
            ids.append(value["playerId"])
    return ids[:2]


def _description(play: dict[str, Any], details: dict[str, Any]) -> str:
    desc = details.get("descKey") or play.get("typeDescKey") or ""
    event_id = play.get("eventId")
    return f"{desc} event_id={event_id}" if event_id is not None else str(desc)


def _clock_to_seconds(value: Any) -> int | None:
    if not value or ":" not in str(value):
        return None
    minutes, seconds = str(value).split(":", 1)
    try:
        return int(minutes) * 60 + int(seconds)
    except ValueError:
        return None


def _game_seconds(period: Any, period_time: Any) -> int | None:
    elapsed = _clock_to_seconds(period_time)
    if elapsed is None or period is None:
        return None
    try:
        period_number = int(period)
    except (TypeError, ValueError):
        return None
    if period_number <= 3:
        return (period_number - 1) * 1200 + elapsed
    return 3600 + (period_number - 4) * 300 + elapsed
