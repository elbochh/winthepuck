from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from config import PROCESSED_DIR, RAW_DIR
from src.utils import default_text, read_json, save_csv

TEAM_GAME_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "team",
    "opponent",
    "is_home",
    "goals_for",
    "goals_against",
    "shots_for",
    "shots_against",
    "powerplay_goals",
    "powerplay_opportunities",
    "penalty_minutes",
    "faceoff_win_pct",
    "blocked_shots",
    "hits",
    "giveaways",
    "takeaways",
]

PLAYER_GAME_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "team",
    "opponent",
    "player_id",
    "player_name",
    "position",
    "goals",
    "assists",
    "points",
    "shots",
    "hits",
    "blocked_shots",
    "pim",
    "plus_minus",
    "time_on_ice",
]

GOALIE_GAME_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "team",
    "opponent",
    "player_id",
    "goalie_name",
    "shots_against",
    "saves",
    "goals_against",
    "save_pct",
    "decision",
    "time_on_ice",
]


def flatten_boxscores(games_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    games_by_id = {int(row.game_id): row._asdict() for row in games_df.itertuples(index=False)}
    team_rows: list[dict[str, Any]] = []
    player_rows: list[dict[str, Any]] = []
    goalie_rows: list[dict[str, Any]] = []
    shift_rows: list[dict[str, Any]] = []
    matchup_rows: list[dict[str, Any]] = []

    for game_id, game in games_by_id.items():
        season = int(game["season"])
        game_dir = RAW_DIR / "games" / str(season) / str(game_id)
        boxscore = _read_optional(game_dir / "boxscore.json")
        right_rail = _read_optional(game_dir / "right_rail.json")
        shifts = _read_optional(game_dir / "shift_charts.json")
        if boxscore:
            team_rows.extend(_team_rows(game, boxscore, right_rail))
            player_rows.extend(_player_rows(game, boxscore))
            goalie_rows.extend(_goalie_rows(game, boxscore))
        if shifts:
            shift_rows.extend(_shift_rows(game_id, season, shifts))
        if right_rail:
            matchup_rows.extend(_matchup_rows(game_id, season, right_rail))

    team_df = save_csv(PROCESSED_DIR / "team_game_stats.csv", team_rows, TEAM_GAME_COLUMNS)
    player_df = save_csv(PROCESSED_DIR / "player_game_stats.csv", player_rows, PLAYER_GAME_COLUMNS)
    goalie_df = save_csv(PROCESSED_DIR / "goalie_game_stats.csv", goalie_rows, GOALIE_GAME_COLUMNS)
    save_csv(PROCESSED_DIR / "shift_charts.csv", shift_rows)
    save_csv(PROCESSED_DIR / "gamecenter_matchups.csv", matchup_rows)
    return team_df, player_df, goalie_df


def _read_optional(path: Path) -> Any | None:
    if not path.exists():
        return None
    return read_json(path)


def _team_rows(game: dict[str, Any], boxscore: dict[str, Any], right_rail: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows = []
    rail_stats = _right_rail_team_stats(right_rail)
    for side, opponent_side, is_home in (("homeTeam", "awayTeam", 1), ("awayTeam", "homeTeam", 0)):
        side_key = "home" if is_home else "away"
        opponent_key = "away" if is_home else "home"
        team = boxscore.get(side, {})
        opponent = boxscore.get(opponent_side, {})
        player_groups = (boxscore.get("playerByGameStats") or {}).get(side, {})
        skaters = list(player_groups.get("forwards", [])) + list(player_groups.get("defense", []))
        faceoff_values = [
            player.get("faceoffWinningPctg")
            for player in skaters
            if player.get("faceoffWinningPctg") is not None and player.get("faceoffWinningPctg") > 0
        ]
        rows.append(
            {
                "game_id": game["game_id"],
                "season": game["season"],
                "game_date": game["game_date"],
                "team": team.get("abbrev") or game["home_team" if is_home else "away_team"],
                "opponent": opponent.get("abbrev") or game["away_team" if is_home else "home_team"],
                "is_home": is_home,
                "goals_for": team.get("score"),
                "goals_against": opponent.get("score"),
                "shots_for": _number(rail_stats.get(("sog", side_key)), team.get("sog")),
                "shots_against": _number(rail_stats.get(("sog", opponent_key)), opponent.get("sog")),
                "powerplay_goals": _number(
                    _power_play_part(rail_stats.get(("powerPlay", side_key)), 0),
                    _sum(skaters, "powerPlayGoals"),
                ),
                "powerplay_opportunities": _power_play_part(rail_stats.get(("powerPlay", side_key)), 1),
                "penalty_minutes": _number(rail_stats.get(("pim", side_key)), _sum(skaters, "pim")),
                "faceoff_win_pct": _number(
                    rail_stats.get(("faceoffWinningPctg", side_key)),
                    sum(faceoff_values) / len(faceoff_values) if faceoff_values else None,
                ),
                "blocked_shots": _number(rail_stats.get(("blockedShots", side_key)), _sum(skaters, "blockedShots")),
                "hits": _number(rail_stats.get(("hits", side_key)), _sum(skaters, "hits")),
                "giveaways": _number(rail_stats.get(("giveaways", side_key)), _sum(skaters, "giveaways")),
                "takeaways": _number(rail_stats.get(("takeaways", side_key)), _sum(skaters, "takeaways")),
            }
        )
    return rows


def _player_rows(game: dict[str, Any], boxscore: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for side, is_home in (("homeTeam", 1), ("awayTeam", 0)):
        team = boxscore.get(side, {}).get("abbrev") or game["home_team" if is_home else "away_team"]
        opponent = game["away_team" if is_home else "home_team"]
        groups = (boxscore.get("playerByGameStats") or {}).get(side, {})
        for player in list(groups.get("forwards", [])) + list(groups.get("defense", [])):
            rows.append(
                {
                    "game_id": game["game_id"],
                    "season": game["season"],
                    "game_date": game["game_date"],
                    "team": team,
                    "opponent": opponent,
                    "player_id": player.get("playerId"),
                    "player_name": default_text(player.get("name")),
                    "position": player.get("position"),
                    "goals": player.get("goals"),
                    "assists": player.get("assists"),
                    "points": player.get("points"),
                    "shots": player.get("sog"),
                    "hits": player.get("hits"),
                    "blocked_shots": player.get("blockedShots"),
                    "pim": player.get("pim"),
                    "plus_minus": player.get("plusMinus"),
                    "time_on_ice": player.get("toi"),
                }
            )
    return rows


def _goalie_rows(game: dict[str, Any], boxscore: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for side, is_home in (("homeTeam", 1), ("awayTeam", 0)):
        team = boxscore.get(side, {}).get("abbrev") or game["home_team" if is_home else "away_team"]
        opponent = game["away_team" if is_home else "home_team"]
        groups = (boxscore.get("playerByGameStats") or {}).get(side, {})
        for goalie in groups.get("goalies", []):
            rows.append(
                {
                    "game_id": game["game_id"],
                    "season": game["season"],
                    "game_date": game["game_date"],
                    "team": team,
                    "opponent": opponent,
                    "player_id": goalie.get("playerId"),
                    "goalie_name": default_text(goalie.get("name")),
                    "shots_against": goalie.get("shotsAgainst"),
                    "saves": goalie.get("saves"),
                    "goals_against": goalie.get("goalsAgainst"),
                    "save_pct": goalie.get("savePctg") or goalie.get("savePct"),
                    "decision": goalie.get("decision"),
                    "time_on_ice": goalie.get("toi"),
                }
            )
    return rows


def _shift_rows(game_id: int, season: int, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("data", []):
        flattened = dict(row)
        flattened["game_id"] = game_id
        flattened["season"] = season
        rows.append(flattened)
    return rows


def _matchup_rows(game_id: int, season: int, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for game in payload.get("seasonSeries", []):
        rows.append(
            {
                "game_id": game_id,
                "season": season,
                "matchup_game_id": game.get("id"),
                "matchup_game_date": game.get("gameDate"),
                "away_team": (game.get("awayTeam") or {}).get("abbrev"),
                "home_team": (game.get("homeTeam") or {}).get("abbrev"),
                "away_score": (game.get("awayTeam") or {}).get("score"),
                "home_score": (game.get("homeTeam") or {}).get("score"),
                "game_state": game.get("gameState"),
            }
        )
    game_info = payload.get("gameInfo") or {}
    if game_info:
        rows.append({"game_id": game_id, "season": season, "matchup_game_id": None, "game_info": str(game_info)})
    return rows


def _sum(rows: list[dict[str, Any]], key: str) -> int:
    return int(sum(row.get(key) or 0 for row in rows))


def _right_rail_team_stats(payload: dict[str, Any] | None) -> dict[tuple[str, str], Any]:
    stats: dict[tuple[str, str], Any] = {}
    for row in (payload or {}).get("teamGameStats", []) or []:
        category = row.get("category")
        if not category:
            continue
        stats[(category, "away")] = row.get("awayValue")
        stats[(category, "home")] = row.get("homeValue")
    return stats


def _power_play_part(value: Any, index: int) -> int | None:
    if not isinstance(value, str) or "/" not in value:
        return None
    parts = value.split("/", 1)
    try:
        return int(parts[index])
    except (IndexError, ValueError):
        return None


def _number(*values: Any) -> float | None:
    for value in values:
        if value is not None and not pd.isna(value):
            return float(value)
    return None
