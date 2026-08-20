from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from config import COMPLETED_GAME_STATES, PROCESSED_DIR, REGULAR_SEASON_GAME_TYPE
from src.utils import parse_date, save_csv, validate_no_feature_leakage


FEATURE_COLUMNS = [
    "game_id",
    "date",
    "home_team",
    "away_team",
    "home_win",
    "home_rest_days",
    "away_rest_days",
    "home_back_to_back",
    "away_back_to_back",
    "home_last_5_win_pct",
    "away_last_5_win_pct",
    "home_last_10_win_pct",
    "away_last_10_win_pct",
    "home_last_5_goals_for_avg",
    "away_last_5_goals_for_avg",
    "home_last_5_goals_against_avg",
    "away_last_5_goals_against_avg",
    "home_last_10_shots_for_avg",
    "away_last_10_shots_for_avg",
    "home_last_10_shots_against_avg",
    "away_last_10_shots_against_avg",
    "home_season_points_pct_before_game",
    "away_season_points_pct_before_game",
    "home_goal_diff_last_10",
    "away_goal_diff_last_10",
]


def build_model_features() -> tuple[pd.DataFrame, bool]:
    games = pd.read_csv(PROCESSED_DIR / "games.csv")
    team_stats = _load_team_game_stats()
    games = games[
        (games["game_type"] == REGULAR_SEASON_GAME_TYPE)
        & (games["game_state"].isin(COMPLETED_GAME_STATES))
        & (games["home_win"].notna())
    ].copy()
    if games.empty:
        df = save_csv(PROCESSED_DIR / "model_features.csv", [], FEATURE_COLUMNS)
        return df, True

    games["sort_date"] = pd.to_datetime(games["game_date"])
    games = games.sort_values(["sort_date", "start_time_utc", "game_id"])

    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    debug_rows: list[dict[str, Any]] = []

    for game in games.itertuples(index=False):
        game_date = parse_date(game.game_date)
        home_history = _prior_games(history[game.home_team], game_date)
        away_history = _prior_games(history[game.away_team], game_date)
        home = _features_for_team(home_history, game.season, game_date)
        away = _features_for_team(away_history, game.season, game_date)

        rows.append(
            {
                "game_id": game.game_id,
                "date": game.game_date,
                "home_team": game.home_team,
                "away_team": game.away_team,
                "home_win": int(game.home_win),
                "home_rest_days": home["rest_days"],
                "away_rest_days": away["rest_days"],
                "home_back_to_back": home["back_to_back"],
                "away_back_to_back": away["back_to_back"],
                "home_last_5_win_pct": home["last_5_win_pct"],
                "away_last_5_win_pct": away["last_5_win_pct"],
                "home_last_10_win_pct": home["last_10_win_pct"],
                "away_last_10_win_pct": away["last_10_win_pct"],
                "home_last_5_goals_for_avg": home["last_5_goals_for_avg"],
                "away_last_5_goals_for_avg": away["last_5_goals_for_avg"],
                "home_last_5_goals_against_avg": home["last_5_goals_against_avg"],
                "away_last_5_goals_against_avg": away["last_5_goals_against_avg"],
                "home_last_10_shots_for_avg": home["last_10_shots_for_avg"],
                "away_last_10_shots_for_avg": away["last_10_shots_for_avg"],
                "home_last_10_shots_against_avg": home["last_10_shots_against_avg"],
                "away_last_10_shots_against_avg": away["last_10_shots_against_avg"],
                "home_season_points_pct_before_game": home["season_points_pct"],
                "away_season_points_pct_before_game": away["season_points_pct"],
                "home_goal_diff_last_10": home["goal_diff_last_10"],
                "away_goal_diff_last_10": away["goal_diff_last_10"],
            }
        )
        debug_rows.append(
            {
                "game_date": game.game_date,
                "source_dates": [row["game_date"] for row in home_history + away_history],
            }
        )

        _append_history(history, game, team_stats)

    df = save_csv(PROCESSED_DIR / "model_features.csv", rows, FEATURE_COLUMNS)
    return df, validate_no_feature_leakage(debug_rows)


def _load_team_game_stats() -> dict[tuple[int, str], dict[str, Any]]:
    path = PROCESSED_DIR / "team_game_stats.csv"
    if not path.exists():
        return {}
    stats = pd.read_csv(path)
    return {
        (int(row.game_id), row.team): row._asdict()
        for row in stats.itertuples(index=False)
        if pd.notna(row.game_id) and pd.notna(row.team)
    }


def _append_history(
    history: dict[str, list[dict[str, Any]]],
    game: Any,
    team_stats: dict[tuple[int, str], dict[str, Any]],
) -> None:
    for team, opponent, goals_for, goals_against, is_home in (
        (game.home_team, game.away_team, game.home_score, game.away_score, 1),
        (game.away_team, game.home_team, game.away_score, game.home_score, 0),
    ):
        stats = team_stats.get((int(game.game_id), team), {})
        history[team].append(
            {
                "game_id": int(game.game_id),
                "season": int(game.season),
                "game_date": game.game_date,
                "opponent": opponent,
                "is_home": is_home,
                "goals_for": _number(stats.get("goals_for"), goals_for),
                "goals_against": _number(stats.get("goals_against"), goals_against),
                "shots_for": _number(stats.get("shots_for")),
                "shots_against": _number(stats.get("shots_against")),
                "win": int(goals_for > goals_against),
                "points": 2 if goals_for > goals_against else 0,
            }
        )


def _prior_games(history: list[dict[str, Any]], current_date: Any) -> list[dict[str, Any]]:
    return [row for row in history if parse_date(row["game_date"]) < current_date]


def _features_for_team(history: list[dict[str, Any]], season: int, current_game_date: Any) -> dict[str, Any]:
    sorted_history = sorted(history, key=lambda row: (row["game_date"], row["game_id"]))
    last_5 = sorted_history[-5:]
    last_10 = sorted_history[-10:]
    season_history = [row for row in sorted_history if int(row["season"]) == int(season)]
    rest_days = None
    if sorted_history:
        last_date = parse_date(sorted_history[-1]["game_date"])
        if last_date and current_game_date:
            rest_days = (current_game_date - last_date).days

    values = {
        "rest_days": rest_days,
        "back_to_back": int(rest_days == 1) if rest_days is not None else 0,
        "last_5_win_pct": _avg(last_5, "win"),
        "last_10_win_pct": _avg(last_10, "win"),
        "last_5_goals_for_avg": _avg(last_5, "goals_for"),
        "last_5_goals_against_avg": _avg(last_5, "goals_against"),
        "last_10_shots_for_avg": _avg(last_10, "shots_for"),
        "last_10_shots_against_avg": _avg(last_10, "shots_against"),
        "season_points_pct": _season_points_pct(season_history),
        "goal_diff_last_10": _goal_diff(last_10),
    }
    if sorted_history:
        values["last_prior_date"] = sorted_history[-1]["game_date"]
    return values


def _avg(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row.get(key) for row in rows if row.get(key) is not None and not pd.isna(row.get(key))]
    return round(float(sum(values) / len(values)), 4) if values else None


def _season_points_pct(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    return round(float(sum(row.get("points", 0) for row in rows) / (2 * len(rows))), 4)


def _goal_diff(rows: list[dict[str, Any]]) -> float | None:
    values = [
        (row.get("goals_for") or 0) - (row.get("goals_against") or 0)
        for row in rows
        if row.get("goals_for") is not None and row.get("goals_against") is not None
    ]
    return round(float(sum(values)), 4) if values else None


def _number(*values: Any) -> float | None:
    for value in values:
        if value is not None and not pd.isna(value):
            return float(value)
    return None
