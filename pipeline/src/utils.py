from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from config import LOG_DIR


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "pipeline.log"),
            logging.StreamHandler(),
        ],
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def save_csv(path: Path, rows: Iterable[dict[str, Any]], columns: list[str] | None = None) -> pd.DataFrame:
    ensure_parent(path)
    df = pd.DataFrame(list(rows))
    if columns is not None:
        for column in columns:
            if column not in df.columns:
                df[column] = None
        df = df[columns]
    df.to_csv(path, index=False)
    return df


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def default_text(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("default") or next(iter(value.values()), None)
    return value


def nested(payload: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    current: Any = payload or {}
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def date_range(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(days + 1)]


def season_start_date(season: int) -> date:
    start_year = int(str(season)[:4])
    return date(start_year, 10, 1)


def season_end_date(season: int) -> date:
    end_year = int(str(season)[4:])
    return date(end_year, 6, 30)


def monthly_snapshot_dates(season: int, stop_date: date | None = None) -> list[date]:
    start = season_start_date(season)
    end = min(season_end_date(season), stop_date) if stop_date else season_end_date(season)
    snapshots = [start]
    month = 11
    year = start.year
    while date(year, month, 1) <= end:
        snapshots.append(date(year, month, 1))
        month += 1
        if month == 13:
            month = 1
            year += 1
    if end not in snapshots:
        snapshots.append(end)
    return snapshots


def count_duplicate_game_ids(games_csv: Path) -> int:
    df = load_csv(games_csv)
    if df.empty or "game_id" not in df.columns:
        return 0
    return int(df["game_id"].duplicated().sum())


def count_missing_game_files(raw_games_dir: Path, games: pd.DataFrame, filename: str) -> int:
    if games.empty or "game_id" not in games.columns or "season" not in games.columns:
        return 0
    missing = 0
    for row in games.itertuples(index=False):
        path = raw_games_dir / str(row.season) / str(row.game_id) / filename
        if not path.exists():
            missing += 1
    return missing


def required_columns_present(path: Path, required: list[str]) -> tuple[bool, list[str]]:
    df = load_csv(path)
    missing = [column for column in required if column not in df.columns]
    return not missing, missing


def validate_no_feature_leakage(feature_debug_rows: Iterable[dict[str, Any]]) -> bool:
    for row in feature_debug_rows:
        game_date = parse_date(row.get("game_date"))
        for source_date in row.get("source_dates", []):
            parsed_source = parse_date(source_date)
            if game_date is not None and parsed_source is not None and parsed_source >= game_date:
                return False
    return True
