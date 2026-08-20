from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
from tqdm import tqdm

from config import COMPLETED_GAME_STATES, PROCESSED_DIR, RAW_DIR
from src.nhl_client import NHLClient
from src.utils import date_range, default_text, save_csv


GAMES_COLUMNS = [
    "game_id",
    "season",
    "game_type",
    "game_date",
    "venue",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "home_win",
    "game_state",
    "start_time_utc",
]

UPCOMING_COLUMNS = [
    "game_id",
    "game_date",
    "start_time_utc",
    "home_team",
    "away_team",
    "venue",
    "game_state",
]


def fetch_team_schedule(client: NHLClient, team_abbrev: str, season: int) -> list[dict[str, Any]]:
    payload = client.get_web(
        f"club-schedule-season/{team_abbrev}/{season}",
        RAW_DIR / "schedules" / str(season) / f"{team_abbrev}.json",
        optional=True,
    )
    return (payload or {}).get("games", [])


def fetch_season_schedules(client: NHLClient, season: int, team_abbrevs: list[str]) -> list[dict[str, Any]]:
    games_by_id: dict[int, dict[str, Any]] = {}
    for team in tqdm(team_abbrevs, desc=f"Schedules {season}"):
        for game in fetch_team_schedule(client, team, season):
            game_id = game.get("id")
            if game_id is not None:
                games_by_id[int(game_id)] = game
    return sorted(games_by_id.values(), key=lambda game: (game.get("gameDate", ""), game.get("id", 0)))


def flatten_game(game: dict[str, Any]) -> dict[str, Any]:
    home = game.get("homeTeam") or {}
    away = game.get("awayTeam") or {}
    home_score = home.get("score")
    away_score = away.get("score")
    game_state = game.get("gameState")
    home_win = None
    if game_state in COMPLETED_GAME_STATES and home_score is not None and away_score is not None:
        home_win = int(home_score > away_score)
    return {
        "game_id": game.get("id"),
        "season": game.get("season"),
        "game_type": game.get("gameType"),
        "game_date": game.get("gameDate"),
        "venue": default_text(game.get("venue")),
        "home_team": home.get("abbrev"),
        "away_team": away.get("abbrev"),
        "home_score": home_score,
        "away_score": away_score,
        "home_win": home_win,
        "game_state": game_state,
        "start_time_utc": game.get("startTimeUTC"),
    }


def write_games_csv(all_games: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [flatten_game(game) for game in all_games]
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates("game_id").sort_values(["season", "game_date", "game_id"])
    for column in GAMES_COLUMNS:
        if column not in df.columns:
            df[column] = None
    df = df[GAMES_COLUMNS]
    df.to_csv(PROCESSED_DIR / "games.csv", index=False)
    return df


def split_upcoming(games_df: pd.DataFrame) -> pd.DataFrame:
    if games_df.empty:
        return save_csv(PROCESSED_DIR / "upcoming_games.csv", [], UPCOMING_COLUMNS)
    upcoming = games_df[~games_df["game_state"].isin(COMPLETED_GAME_STATES)].copy()
    upcoming = upcoming[["game_id", "game_date", "start_time_utc", "home_team", "away_team", "venue", "game_state"]]
    upcoming.to_csv(PROCESSED_DIR / "upcoming_games.csv", index=False)
    return upcoming


def fetch_daily_schedule(client: NHLClient, target_date: date) -> list[dict[str, Any]]:
    payload = client.get_web(
        f"schedule/{target_date.isoformat()}",
        RAW_DIR / "upcoming" / "schedule" / f"{target_date.isoformat()}.json",
        optional=True,
    )
    games: list[dict[str, Any]] = []
    for day in (payload or {}).get("gameWeek", []):
        games.extend(day.get("games", []))
    return games


def fetch_daily_score(client: NHLClient, target_date: date) -> list[dict[str, Any]]:
    payload = client.get_web(
        f"score/{target_date.isoformat()}",
        RAW_DIR / "upcoming" / "score" / f"{target_date.isoformat()}.json",
        optional=True,
    )
    return (payload or {}).get("games", [])


def fetch_upcoming(client: NHLClient, start_date: date, days_ahead: int) -> pd.DataFrame:
    end_date = start_date + timedelta(days=days_ahead)
    games_by_id: dict[int, dict[str, Any]] = {}
    for target_date in tqdm(date_range(start_date, end_date), desc="Upcoming"):
        for game in fetch_daily_schedule(client, target_date):
            game_id = game.get("id")
            if game_id is not None:
                games_by_id[int(game_id)] = game
        fetch_daily_score(client, target_date)
    rows = [
        flatten_game(game)
        for game in games_by_id.values()
        if game.get("gameState") not in COMPLETED_GAME_STATES
    ]
    df = pd.DataFrame(rows)
    for column in UPCOMING_COLUMNS:
        if column not in df.columns:
            df[column] = None
    if not df.empty:
        df = df.sort_values(["game_date", "start_time_utc", "game_id"])
    df = df[UPCOMING_COLUMNS]
    df.to_csv(PROCESSED_DIR / "upcoming_games.csv", index=False)
    return df
