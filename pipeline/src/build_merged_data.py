from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from config import COMPLETED_GAME_STATES, PROCESSED_DIR
from src.utils import parse_date, save_csv

PREDICTION_GAME_TYPES = {2, 3}
EVEN_STRENGTH_CODE = 1551

TEAM_FEATURES = [
    "rest_days",
    "games_last_3_days",
    "games_last_7_days",
    "games_last_14_days",
    "back_to_back",
    "last_5_win_pct",
    "last_10_win_pct",
    "last_5_goals_for_avg",
    "last_5_goals_against_avg",
    "last_10_shots_for_avg",
    "last_10_shots_against_avg",
    "season_points_pct_before_game",
    "goal_diff_last_10",
    "home_win_pct_before_game",
    "road_win_pct_before_game",
    "home_goal_diff_avg_before_game",
    "road_goal_diff_avg_before_game",
    "last_10_powerplay_goals_avg",
    "last_10_penalty_minutes_avg",
    "last_10_faceoff_win_pct_avg",
    "last_10_blocked_shots_avg",
    "last_10_hits_avg",
    "last_10_giveaways_avg",
    "last_10_takeaways_avg",
    "last_10_es_shot_attempts_for_avg",
    "last_10_es_shot_attempts_against_avg",
    "last_10_es_shot_attempt_share",
    "last_10_es_goals_for_avg",
    "last_10_es_goals_against_avg",
    "last_10_skaters_points_avg",
    "last_10_skaters_shots_avg",
    "last_10_skaters_avg_toi_seconds",
    "last_starting_goalie_id",
    "last_starting_goalie_name",
    "last_3_starting_goalie_save_pct",
    "last_3_starting_goalie_goals_against_avg",
    "last_3_starting_goalie_shots_against_avg",
    "last_3_starting_goalie_quality_start_pct",
]

DIFF_PAIRS = {
    "rest_days_diff": ("home_rest_days", "away_rest_days"),
    "games_last_3_days_diff": ("home_games_last_3_days", "away_games_last_3_days"),
    "games_last_7_days_diff": ("home_games_last_7_days", "away_games_last_7_days"),
    "games_last_14_days_diff": ("home_games_last_14_days", "away_games_last_14_days"),
    "back_to_back_diff": ("home_back_to_back", "away_back_to_back"),
    "last_5_win_pct_diff": ("home_last_5_win_pct", "away_last_5_win_pct"),
    "last_10_win_pct_diff": ("home_last_10_win_pct", "away_last_10_win_pct"),
    "last_5_goals_for_avg_diff": ("home_last_5_goals_for_avg", "away_last_5_goals_for_avg"),
    "last_5_goals_against_avg_diff": (
        "home_last_5_goals_against_avg",
        "away_last_5_goals_against_avg",
    ),
    "last_10_shots_for_avg_diff": ("home_last_10_shots_for_avg", "away_last_10_shots_for_avg"),
    "last_10_shots_against_avg_diff": (
        "home_last_10_shots_against_avg",
        "away_last_10_shots_against_avg",
    ),
    "season_points_pct_diff": (
        "home_season_points_pct_before_game",
        "away_season_points_pct_before_game",
    ),
    "goal_diff_last_10_diff": ("home_goal_diff_last_10", "away_goal_diff_last_10"),
    "home_ice_split_win_pct_diff": (
        "home_home_win_pct_before_game",
        "away_road_win_pct_before_game",
    ),
    "home_ice_split_goal_diff_avg_diff": (
        "home_home_goal_diff_avg_before_game",
        "away_road_goal_diff_avg_before_game",
    ),
    "last_10_powerplay_goals_avg_diff": (
        "home_last_10_powerplay_goals_avg",
        "away_last_10_powerplay_goals_avg",
    ),
    "last_10_penalty_minutes_avg_diff": (
        "home_last_10_penalty_minutes_avg",
        "away_last_10_penalty_minutes_avg",
    ),
    "last_10_faceoff_win_pct_avg_diff": (
        "home_last_10_faceoff_win_pct_avg",
        "away_last_10_faceoff_win_pct_avg",
    ),
    "last_10_blocked_shots_avg_diff": (
        "home_last_10_blocked_shots_avg",
        "away_last_10_blocked_shots_avg",
    ),
    "last_10_hits_avg_diff": ("home_last_10_hits_avg", "away_last_10_hits_avg"),
    "last_10_giveaways_avg_diff": ("home_last_10_giveaways_avg", "away_last_10_giveaways_avg"),
    "last_10_takeaways_avg_diff": ("home_last_10_takeaways_avg", "away_last_10_takeaways_avg"),
    "last_10_es_shot_attempts_for_avg_diff": (
        "home_last_10_es_shot_attempts_for_avg",
        "away_last_10_es_shot_attempts_for_avg",
    ),
    "last_10_es_shot_attempts_against_avg_diff": (
        "home_last_10_es_shot_attempts_against_avg",
        "away_last_10_es_shot_attempts_against_avg",
    ),
    "last_10_es_shot_attempt_share_diff": (
        "home_last_10_es_shot_attempt_share",
        "away_last_10_es_shot_attempt_share",
    ),
    "last_10_es_goals_for_avg_diff": (
        "home_last_10_es_goals_for_avg",
        "away_last_10_es_goals_for_avg",
    ),
    "last_10_es_goals_against_avg_diff": (
        "home_last_10_es_goals_against_avg",
        "away_last_10_es_goals_against_avg",
    ),
    "last_10_skaters_points_avg_diff": (
        "home_last_10_skaters_points_avg",
        "away_last_10_skaters_points_avg",
    ),
    "last_10_skaters_shots_avg_diff": (
        "home_last_10_skaters_shots_avg",
        "away_last_10_skaters_shots_avg",
    ),
    "last_10_skaters_avg_toi_seconds_diff": (
        "home_last_10_skaters_avg_toi_seconds",
        "away_last_10_skaters_avg_toi_seconds",
    ),
    "last_3_starting_goalie_save_pct_diff": (
        "home_last_3_starting_goalie_save_pct",
        "away_last_3_starting_goalie_save_pct",
    ),
    "last_3_starting_goalie_goals_against_avg_diff": (
        "home_last_3_starting_goalie_goals_against_avg",
        "away_last_3_starting_goalie_goals_against_avg",
    ),
    "last_3_starting_goalie_shots_against_avg_diff": (
        "home_last_3_starting_goalie_shots_against_avg",
        "away_last_3_starting_goalie_shots_against_avg",
    ),
    "last_3_starting_goalie_quality_start_pct_diff": (
        "home_last_3_starting_goalie_quality_start_pct",
        "away_last_3_starting_goalie_quality_start_pct",
    ),
}

BASE_COLUMNS = [
    "game_id",
    "season",
    "game_type",
    "game_date",
    "start_time_utc",
    "venue",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "winner_team",
    "target_home_win",
]

H2H_COLUMNS = [
    "h2h_games_last_365_days",
    "h2h_home_team_win_pct_last_5",
    "h2h_home_team_goal_diff_avg_last_5",
]

PLAYOFF_COLUMNS = [
    "playoff_series_game_number",
    "home_series_wins_before",
    "away_series_wins_before",
    "series_win_diff_before",
    "home_elimination_game",
    "away_elimination_game",
]

MERGED_COLUMNS = (
    BASE_COLUMNS
    + [f"home_{column}" for column in TEAM_FEATURES]
    + [f"away_{column}" for column in TEAM_FEATURES]
    + list(DIFF_PAIRS)
    + H2H_COLUMNS
    + PLAYOFF_COLUMNS
)


def build_merged_model_data() -> pd.DataFrame:
    games = pd.read_csv(PROCESSED_DIR / "games.csv")
    team_stats = _load_team_game_stats()
    play_by_play_stats = _load_play_by_play_team_stats()
    goalie_starters = _load_goalie_starters()
    player_stats = _load_player_team_game_stats()
    games = games[
        (games["game_type"].isin(PREDICTION_GAME_TYPES))
        & (games["game_state"].isin(COMPLETED_GAME_STATES))
        & (games["home_win"].notna())
    ].copy()
    if games.empty:
        return save_csv(PROCESSED_DIR / "merged_model_data.csv", [], MERGED_COLUMNS)

    games["sort_date"] = pd.to_datetime(games["game_date"])
    games = games.sort_values(["sort_date", "start_time_utc", "game_id"])

    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    matchup_history: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    playoff_series_history: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    rows: list[dict[str, Any]] = []

    for game in games.itertuples(index=False):
        game_date = parse_date(game.game_date)
        home_history = _prior_games(history[game.home_team], game_date)
        away_history = _prior_games(history[game.away_team], game_date)
        home = _features_for_team(home_history, int(game.season), game_date)
        away = _features_for_team(away_history, int(game.season), game_date)

        row = {
            "game_id": int(game.game_id),
            "season": int(game.season),
            "game_type": int(game.game_type),
            "game_date": game.game_date,
            "start_time_utc": game.start_time_utc,
            "venue": game.venue,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "winner_team": game.home_team if int(game.home_win) == 1 else game.away_team,
            "target_home_win": int(game.home_win),
        }
        row.update(_prefix_features("home", home))
        row.update(_prefix_features("away", away))
        row.update(_diff_features(row))
        row.update(_h2h_features(matchup_history[_pair_key(game.home_team, game.away_team)], game.home_team, game_date))
        row.update(_playoff_features(playoff_series_history, game))
        rows.append(row)

        _append_history(history, game, team_stats, play_by_play_stats, goalie_starters, player_stats)
        _append_matchup_history(matchup_history, game)
        _append_playoff_series_history(playoff_series_history, game)

    return save_csv(PROCESSED_DIR / "merged_model_data.csv", rows, MERGED_COLUMNS)


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


def _load_play_by_play_team_stats() -> dict[tuple[int, str], dict[str, Any]]:
    path = PROCESSED_DIR / "play_by_play.csv"
    if not path.exists():
        return {}

    usecols = ["game_id", "team", "event_type", "strength"]
    events = pd.read_csv(path, usecols=usecols, low_memory=False)
    events = events[events["team"].notna()].copy()
    events["is_shot_attempt"] = events["event_type"].isin(["shot-on-goal", "missed-shot", "goal"]).astype(int)
    events["is_shot_on_goal"] = events["event_type"].isin(["shot-on-goal", "goal"]).astype(int)
    events["is_goal"] = (events["event_type"] == "goal").astype(int)
    events["is_even_strength"] = (events["strength"].fillna(0).astype(int) == EVEN_STRENGTH_CODE).astype(int)
    events["es_shot_attempts"] = events["is_shot_attempt"] * events["is_even_strength"]
    events["es_shots_on_goal"] = events["is_shot_on_goal"] * events["is_even_strength"]
    events["es_goals"] = events["is_goal"] * events["is_even_strength"]

    grouped = (
        events.groupby(["game_id", "team"], dropna=False)[
            ["is_shot_attempt", "is_shot_on_goal", "is_goal", "es_shot_attempts", "es_shots_on_goal", "es_goals"]
        ]
        .sum()
        .reset_index()
    )
    grouped = grouped.rename(
        columns={
            "is_shot_attempt": "shot_attempts",
            "is_shot_on_goal": "shots_on_goal",
            "is_goal": "goals",
        }
    )
    return {
        (int(row.game_id), row.team): row._asdict()
        for row in grouped.itertuples(index=False)
        if pd.notna(row.game_id) and pd.notna(row.team)
    }


def _load_goalie_starters() -> dict[tuple[int, str], dict[str, Any]]:
    path = PROCESSED_DIR / "goalie_game_stats.csv"
    if not path.exists():
        return {}
    goalies = pd.read_csv(path)
    goalies["toi_seconds"] = goalies["time_on_ice"].map(_time_to_seconds)
    idx = goalies.groupby(["game_id", "team"])["toi_seconds"].idxmax()
    starters = goalies.loc[idx].copy()
    starters["quality_start"] = (starters["save_pct"] >= 0.9).astype(float)
    return {
        (int(row.game_id), row.team): row._asdict()
        for row in starters.itertuples(index=False)
        if pd.notna(row.game_id) and pd.notna(row.team)
    }


def _load_player_team_game_stats() -> dict[tuple[int, str], dict[str, Any]]:
    path = PROCESSED_DIR / "player_game_stats.csv"
    if not path.exists():
        return {}
    players = pd.read_csv(path)
    players["toi_seconds"] = players["time_on_ice"].map(_time_to_seconds)
    grouped = (
        players.groupby(["game_id", "team"], dropna=False)
        .agg(
            skater_count=("player_id", "count"),
            skaters_goals=("goals", "sum"),
            skaters_assists=("assists", "sum"),
            skaters_points=("points", "sum"),
            skaters_shots=("shots", "sum"),
            skaters_hits=("hits", "sum"),
            skaters_blocked_shots=("blocked_shots", "sum"),
            skaters_avg_toi_seconds=("toi_seconds", "mean"),
        )
        .reset_index()
    )
    return {
        (int(row.game_id), row.team): row._asdict()
        for row in grouped.itertuples(index=False)
        if pd.notna(row.game_id) and pd.notna(row.team)
    }


def _append_history(
    history: dict[str, list[dict[str, Any]]],
    game: Any,
    team_stats: dict[tuple[int, str], dict[str, Any]],
    play_by_play_stats: dict[tuple[int, str], dict[str, Any]],
    goalie_starters: dict[tuple[int, str], dict[str, Any]],
    player_stats: dict[tuple[int, str], dict[str, Any]],
) -> None:
    for team, opponent, goals_for, goals_against, is_home in (
        (game.home_team, game.away_team, game.home_score, game.away_score, 1),
        (game.away_team, game.home_team, game.away_score, game.home_score, 0),
    ):
        game_id = int(game.game_id)
        stats = team_stats.get((game_id, team), {})
        pbp_for = play_by_play_stats.get((game_id, team), {})
        pbp_against = play_by_play_stats.get((game_id, opponent), {})
        goalie = goalie_starters.get((game_id, team), {})
        players = player_stats.get((game_id, team), {})

        history[team].append(
            {
                "game_id": game_id,
                "season": int(game.season),
                "game_date": game.game_date,
                "opponent": opponent,
                "is_home": is_home,
                "goals_for": _number(stats.get("goals_for"), goals_for),
                "goals_against": _number(stats.get("goals_against"), goals_against),
                "shots_for": _number(stats.get("shots_for")),
                "shots_against": _number(stats.get("shots_against")),
                "powerplay_goals": _number(stats.get("powerplay_goals")),
                "penalty_minutes": _number(stats.get("penalty_minutes")),
                "faceoff_win_pct": _number(stats.get("faceoff_win_pct")),
                "blocked_shots": _number(stats.get("blocked_shots")),
                "hits": _number(stats.get("hits")),
                "giveaways": _number(stats.get("giveaways")),
                "takeaways": _number(stats.get("takeaways")),
                "es_shot_attempts_for": _number(pbp_for.get("es_shot_attempts")),
                "es_shot_attempts_against": _number(pbp_against.get("es_shot_attempts")),
                "es_goals_for": _number(pbp_for.get("es_goals")),
                "es_goals_against": _number(pbp_against.get("es_goals")),
                "skaters_points": _number(players.get("skaters_points")),
                "skaters_shots": _number(players.get("skaters_shots")),
                "skaters_avg_toi_seconds": _number(players.get("skaters_avg_toi_seconds")),
                "starting_goalie_id": _safe_int(goalie.get("player_id")),
                "starting_goalie_name": goalie.get("goalie_name"),
                "starting_goalie_save_pct": _number(goalie.get("save_pct")),
                "starting_goalie_goals_against": _number(goalie.get("goals_against")),
                "starting_goalie_shots_against": _number(goalie.get("shots_against")),
                "starting_goalie_quality_start": _number(goalie.get("quality_start")),
                "win": int(goals_for > goals_against),
                "points": 2 if goals_for > goals_against else 0,
            }
        )


def _append_matchup_history(matchup_history: dict[tuple[str, str], list[dict[str, Any]]], game: Any) -> None:
    matchup_history[_pair_key(game.home_team, game.away_team)].append(
        {
            "game_id": int(game.game_id),
            "game_date": game.game_date,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "winner_team": game.home_team if int(game.home_win) == 1 else game.away_team,
            "goals_by_team": {
                game.home_team: _number(game.home_score),
                game.away_team: _number(game.away_score),
            },
        }
    )


def _append_playoff_series_history(
    playoff_series_history: dict[tuple[int, str], list[dict[str, Any]]],
    game: Any,
) -> None:
    series_key = _playoff_series_key(game)
    if series_key is None:
        return
    playoff_series_history[series_key].append(
        {
            "game_id": int(game.game_id),
            "game_date": game.game_date,
            "winner_team": game.home_team if int(game.home_win) == 1 else game.away_team,
            "home_team": game.home_team,
            "away_team": game.away_team,
        }
    )


def _prior_games(history: list[dict[str, Any]], current_date: Any) -> list[dict[str, Any]]:
    return [row for row in history if parse_date(row["game_date"]) < current_date]


def _features_for_team(history: list[dict[str, Any]], season: int, current_game_date: Any) -> dict[str, Any]:
    sorted_history = sorted(history, key=lambda row: (row["game_date"], row["game_id"]))
    last_3 = sorted_history[-3:]
    last_5 = sorted_history[-5:]
    last_10 = sorted_history[-10:]
    season_history = [row for row in sorted_history if int(row["season"]) == int(season)]
    home_games = [row for row in season_history if int(row["is_home"]) == 1]
    road_games = [row for row in season_history if int(row["is_home"]) == 0]
    rest_days = None
    if sorted_history:
        last_date = parse_date(sorted_history[-1]["game_date"])
        if last_date and current_game_date:
            rest_days = (current_game_date - last_date).days
    last_goalie = sorted_history[-1] if sorted_history else {}

    return {
        "rest_days": rest_days,
        "games_last_3_days": _count_games_within_days(sorted_history, current_game_date, 3),
        "games_last_7_days": _count_games_within_days(sorted_history, current_game_date, 7),
        "games_last_14_days": _count_games_within_days(sorted_history, current_game_date, 14),
        "back_to_back": int(rest_days == 1) if rest_days is not None else 0,
        "last_5_win_pct": _avg(last_5, "win"),
        "last_10_win_pct": _avg(last_10, "win"),
        "last_5_goals_for_avg": _avg(last_5, "goals_for"),
        "last_5_goals_against_avg": _avg(last_5, "goals_against"),
        "last_10_shots_for_avg": _avg(last_10, "shots_for"),
        "last_10_shots_against_avg": _avg(last_10, "shots_against"),
        "season_points_pct_before_game": _season_points_pct(season_history),
        "goal_diff_last_10": _goal_diff(last_10),
        "home_win_pct_before_game": _avg(home_games, "win"),
        "road_win_pct_before_game": _avg(road_games, "win"),
        "home_goal_diff_avg_before_game": _goal_diff_avg(home_games),
        "road_goal_diff_avg_before_game": _goal_diff_avg(road_games),
        "last_10_powerplay_goals_avg": _avg(last_10, "powerplay_goals"),
        "last_10_penalty_minutes_avg": _avg(last_10, "penalty_minutes"),
        "last_10_faceoff_win_pct_avg": _avg(last_10, "faceoff_win_pct"),
        "last_10_blocked_shots_avg": _avg(last_10, "blocked_shots"),
        "last_10_hits_avg": _avg(last_10, "hits"),
        "last_10_giveaways_avg": _avg(last_10, "giveaways"),
        "last_10_takeaways_avg": _avg(last_10, "takeaways"),
        "last_10_es_shot_attempts_for_avg": _avg(last_10, "es_shot_attempts_for"),
        "last_10_es_shot_attempts_against_avg": _avg(last_10, "es_shot_attempts_against"),
        "last_10_es_shot_attempt_share": _shot_attempt_share(last_10),
        "last_10_es_goals_for_avg": _avg(last_10, "es_goals_for"),
        "last_10_es_goals_against_avg": _avg(last_10, "es_goals_against"),
        "last_10_skaters_points_avg": _avg(last_10, "skaters_points"),
        "last_10_skaters_shots_avg": _avg(last_10, "skaters_shots"),
        "last_10_skaters_avg_toi_seconds": _avg(last_10, "skaters_avg_toi_seconds"),
        "last_starting_goalie_id": last_goalie.get("starting_goalie_id"),
        "last_starting_goalie_name": last_goalie.get("starting_goalie_name"),
        "last_3_starting_goalie_save_pct": _avg(last_3, "starting_goalie_save_pct"),
        "last_3_starting_goalie_goals_against_avg": _avg(last_3, "starting_goalie_goals_against"),
        "last_3_starting_goalie_shots_against_avg": _avg(last_3, "starting_goalie_shots_against"),
        "last_3_starting_goalie_quality_start_pct": _avg(last_3, "starting_goalie_quality_start"),
    }


def _h2h_features(history: list[dict[str, Any]], home_team: str, current_game_date: Any) -> dict[str, Any]:
    prior = _prior_games(history, current_game_date)
    last_5 = sorted(prior, key=lambda row: (row["game_date"], row["game_id"]))[-5:]
    home_team_wins = [int(row["winner_team"] == home_team) for row in last_5]
    goal_diffs = []
    for row in last_5:
        goals_by_team = row.get("goals_by_team", {})
        opponent_goals = [goals for team, goals in goals_by_team.items() if team != home_team]
        if goals_by_team.get(home_team) is not None and opponent_goals:
            goal_diffs.append(float(goals_by_team[home_team]) - float(opponent_goals[0]))

    return {
        "h2h_games_last_365_days": _count_games_within_days(prior, current_game_date, 365),
        "h2h_home_team_win_pct_last_5": round(float(sum(home_team_wins) / len(home_team_wins)), 4)
        if home_team_wins
        else None,
        "h2h_home_team_goal_diff_avg_last_5": round(float(sum(goal_diffs) / len(goal_diffs)), 4)
        if goal_diffs
        else None,
    }


def _playoff_features(playoff_series_history: dict[tuple[int, str], list[dict[str, Any]]], game: Any) -> dict[str, Any]:
    series_key = _playoff_series_key(game)
    if series_key is None:
        return {
            "playoff_series_game_number": 0,
            "home_series_wins_before": 0,
            "away_series_wins_before": 0,
            "series_win_diff_before": 0,
            "home_elimination_game": 0,
            "away_elimination_game": 0,
        }

    history = playoff_series_history[series_key]
    home_wins = sum(1 for row in history if row["winner_team"] == game.home_team)
    away_wins = sum(1 for row in history if row["winner_team"] == game.away_team)
    return {
        "playoff_series_game_number": len(history) + 1,
        "home_series_wins_before": home_wins,
        "away_series_wins_before": away_wins,
        "series_win_diff_before": home_wins - away_wins,
        "home_elimination_game": int(away_wins == 3),
        "away_elimination_game": int(home_wins == 3),
    }


def _prefix_features(prefix: str, features: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in features.items()}


def _diff_features(row: dict[str, Any]) -> dict[str, Any]:
    return {column: _subtract(row.get(left), row.get(right)) for column, (left, right) in DIFF_PAIRS.items()}


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


def _goal_diff_avg(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    total = _goal_diff(rows)
    return round(float(total / len(rows)), 4) if total is not None else None


def _shot_attempt_share(rows: list[dict[str, Any]]) -> float | None:
    attempts_for = [row.get("es_shot_attempts_for") for row in rows if row.get("es_shot_attempts_for") is not None]
    attempts_against = [
        row.get("es_shot_attempts_against") for row in rows if row.get("es_shot_attempts_against") is not None
    ]
    total_for = sum(attempts_for)
    total_against = sum(attempts_against)
    denominator = total_for + total_against
    return round(float(total_for / denominator), 4) if denominator else None


def _count_games_within_days(rows: list[dict[str, Any]], current_game_date: Any, days: int) -> int:
    if current_game_date is None:
        return 0
    count = 0
    for row in rows:
        game_date = parse_date(row.get("game_date"))
        if game_date is None:
            continue
        delta = (current_game_date - game_date).days
        if 0 < delta <= days:
            count += 1
    return count


def _playoff_series_key(game: Any) -> tuple[int, str] | None:
    if int(game.game_type) != 3:
        return None
    game_id = str(int(game.game_id))
    series_code = game_id[6:9] if len(game_id) >= 10 else "-".join(sorted([game.home_team, game.away_team]))
    return int(game.season), series_code


def _pair_key(team_a: str, team_b: str) -> tuple[str, str]:
    return tuple(sorted([team_a, team_b]))


def _subtract(left: Any, right: Any) -> float | None:
    if left is None or right is None or pd.isna(left) or pd.isna(right):
        return None
    return round(float(left) - float(right), 4)


def _number(*values: Any) -> float | None:
    for value in values:
        if value is not None and not pd.isna(value):
            return float(value)
    return None


def _safe_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _time_to_seconds(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    parts = str(value).split(":")
    if len(parts) != 2:
        return None
    return float(int(parts[0]) * 60 + int(parts[1]))


if __name__ == "__main__":
    df = build_merged_model_data()
    print(f"Merged model data rows: {len(df)}")
    print(f"Wrote {PROCESSED_DIR / 'merged_model_data.csv'}")
