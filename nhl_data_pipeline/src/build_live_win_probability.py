from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from config import COMPLETED_GAME_STATES, PROCESSED_DIR, RAW_DIR
from src.fetch_live import latest_live_snapshot_dir
from src.utils import default_text, read_json, save_csv


PREDICTION_GAME_TYPES = {2, 3}
SHOT_ATTEMPT_EVENTS = {"shot-on-goal", "missed-shot", "blocked-shot", "goal"}
SHOT_ON_GOAL_EVENTS = {"shot-on-goal", "goal"}
GOAL_EVENT = "goal"
PENALTY_EVENT = "penalty"
FACEOFF_EVENT = "faceoff"
HIT_EVENT = "hit"
GIVEAWAY_EVENT = "giveaway"
TAKEAWAY_EVENT = "takeaway"
BLOCKED_SHOT_EVENT = "blocked-shot"

LIVE_WIN_PROBABILITY_COLUMNS = [
    "game_id",
    "season",
    "game_type",
    "game_date",
    "start_time_utc",
    "venue",
    "game_state",
    "home_team",
    "away_team",
    "event_index",
    "event_id",
    "sort_order",
    "event_type",
    "event_team",
    "event_team_side",
    "period",
    "period_type",
    "time_in_period",
    "time_remaining",
    "seconds_elapsed",
    "seconds_remaining_regulation",
    "seconds_remaining_game",
    "game_progress",
    "situation_code",
    "home_skaters",
    "away_skaters",
    "home_goalie_on_ice",
    "away_goalie_on_ice",
    "home_empty_net",
    "away_empty_net",
    "manpower_diff_home",
    "home_power_play",
    "away_power_play",
    "even_strength",
    "home_score",
    "away_score",
    "score_diff_home",
    "abs_score_diff",
    "home_sog",
    "away_sog",
    "sog_diff_home",
    "home_shot_attempts",
    "away_shot_attempts",
    "shot_attempt_diff_home",
    "home_missed_shots",
    "away_missed_shots",
    "home_blocked_shots_for",
    "away_blocked_shots_for",
    "home_blocks",
    "away_blocks",
    "home_hits",
    "away_hits",
    "hit_diff_home",
    "home_giveaways",
    "away_giveaways",
    "home_takeaways",
    "away_takeaways",
    "home_faceoff_wins",
    "away_faceoff_wins",
    "faceoff_win_diff_home",
    "home_penalties",
    "away_penalties",
    "home_penalty_minutes",
    "away_penalty_minutes",
    "penalty_minute_diff_home",
    "home_active_penalties",
    "away_active_penalties",
    "home_active_penalty_seconds",
    "away_active_penalty_seconds",
    "home_power_play_opportunities",
    "away_power_play_opportunities",
    "home_power_play_goals",
    "away_power_play_goals",
    "home_short_handed_goals",
    "away_short_handed_goals",
    "home_goalie_id",
    "away_goalie_id",
    "home_goalie_saves",
    "away_goalie_saves",
    "home_goalie_goals_against",
    "away_goalie_goals_against",
    "home_goalie_save_pct_live",
    "away_goalie_save_pct_live",
    "x_coord",
    "y_coord",
    "zone_code",
    "shot_type",
    "penalty_type",
    "penalty_minutes_event",
    "reason",
    "shooting_player_id",
    "scoring_player_id",
    "goalie_in_net_id",
    "committed_by_player_id",
    "drawn_by_player_id",
    "home_final_score",
    "away_final_score",
    "target_home_win",
]


def build_live_win_probability_dataset(
    start_season: int | None = None,
    end_season: int | None = None,
    max_games: int | None = None,
) -> pd.DataFrame:
    games = pd.read_csv(PROCESSED_DIR / "games.csv")
    if games.empty:
        return save_csv(PROCESSED_DIR / "live_win_probability_features.csv", [], LIVE_WIN_PROBABILITY_COLUMNS)

    games = games[
        games["game_state"].isin(COMPLETED_GAME_STATES)
        & games["game_type"].isin(PREDICTION_GAME_TYPES)
    ].copy()
    if start_season is not None:
        games = games[games["season"] >= start_season]
    if end_season is not None:
        games = games[games["season"] <= end_season]
    games = games.sort_values(["game_date", "start_time_utc", "game_id"])
    if max_games is not None:
        games = games.tail(max_games)

    rows: list[dict[str, Any]] = []
    for game in tqdm(games.itertuples(index=False), total=len(games), desc="Live WP snapshots"):
        game_dir = RAW_DIR / "games" / str(int(game.season)) / str(int(game.game_id))
        play_by_play_path = game_dir / "play_by_play.json"
        if not play_by_play_path.exists():
            continue
        boxscore = _read_optional(game_dir / "boxscore.json")
        rows.extend(_rows_for_game(read_json(play_by_play_path), boxscore=boxscore, game_row=game))

    return save_csv(PROCESSED_DIR / "live_win_probability_features.csv", rows, LIVE_WIN_PROBABILITY_COLUMNS)


def build_current_live_features() -> pd.DataFrame:
    snapshot_dir = latest_live_snapshot_dir()
    if snapshot_dir is None:
        return save_csv(PROCESSED_DIR / "live_current_features.csv", [], LIVE_WIN_PROBABILITY_COLUMNS)

    rows: list[dict[str, Any]] = []
    for game_dir in sorted((snapshot_dir / "games").glob("*")) if (snapshot_dir / "games").exists() else []:
        play_by_play_path = game_dir / "play_by_play.json"
        landing_path = game_dir / "landing.json"
        if play_by_play_path.exists():
            game_rows = _rows_for_game(
                read_json(play_by_play_path),
                boxscore=_read_optional(game_dir / "boxscore.json"),
                include_target=False,
            )
        elif landing_path.exists():
            game_rows = [_pregame_row(read_json(landing_path), include_target=False)]
        else:
            game_rows = []
        if game_rows:
            rows.append(game_rows[-1])

    return save_csv(PROCESSED_DIR / "live_current_features.csv", rows, LIVE_WIN_PROBABILITY_COLUMNS)


def _rows_for_game(
    payload: dict[str, Any],
    boxscore: dict[str, Any] | None = None,
    game_row: Any | None = None,
    include_target: bool = True,
) -> list[dict[str, Any]]:
    context = _game_context(payload, boxscore, game_row, include_target)
    state = _initial_state(context)
    active_penalties: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    previous_power_play_side: str | None = None

    plays = sorted(payload.get("plays", []) or [], key=lambda play: (play.get("sortOrder") or 0, play.get("eventId") or 0))
    if not plays:
        return [_pregame_row(payload, boxscore=boxscore, game_row=game_row, include_target=include_target)]

    for event_index, play in enumerate(plays, start=1):
        details = play.get("details") or {}
        event_type = play.get("typeDescKey")
        event_team_side = context["team_id_to_side"].get(details.get("eventOwnerTeamId"))
        seconds_elapsed = _game_seconds(
            (play.get("periodDescriptor") or {}).get("number"),
            play.get("timeInPeriod"),
        )
        _expire_penalties(active_penalties, seconds_elapsed)

        situation = _parse_situation(play.get("situationCode"))
        current_power_play_side = _power_play_side(situation)
        if current_power_play_side and current_power_play_side != previous_power_play_side:
            state[f"{current_power_play_side}_power_play_opportunities"] += 1
        if current_power_play_side:
            previous_power_play_side = current_power_play_side
        elif situation.get("even_strength") == 1:
            previous_power_play_side = None

        _apply_event_to_state(state, active_penalties, context, play, details, event_type, event_team_side, seconds_elapsed)

        row = _base_row(context, state, active_penalties, play, details, event_index, situation)
        rows.append(row)

    return rows


def _pregame_row(
    payload: dict[str, Any],
    boxscore: dict[str, Any] | None = None,
    game_row: Any | None = None,
    include_target: bool = True,
) -> dict[str, Any]:
    context = _game_context(payload, boxscore, game_row, include_target)
    state = _initial_state(context)
    play = {
        "eventId": None,
        "sortOrder": 0,
        "typeDescKey": "pregame",
        "periodDescriptor": {"number": 0, "periodType": "PRE"},
        "timeInPeriod": "00:00",
        "timeRemaining": None,
        "situationCode": "1551",
    }
    return _base_row(context, state, [], play, {}, 0, _parse_situation("1551"))


def _game_context(
    payload: dict[str, Any],
    boxscore: dict[str, Any] | None,
    game_row: Any | None,
    include_target: bool,
) -> dict[str, Any]:
    home = payload.get("homeTeam") or {}
    away = payload.get("awayTeam") or {}
    home_abbrev = home.get("abbrev") or getattr(game_row, "home_team", None)
    away_abbrev = away.get("abbrev") or getattr(game_row, "away_team", None)
    expose_outcome = include_target or payload.get("gameState") in COMPLETED_GAME_STATES
    home_final_score = _number(home.get("score"), getattr(game_row, "home_score", None)) if expose_outcome else None
    away_final_score = _number(away.get("score"), getattr(game_row, "away_score", None)) if expose_outcome else None
    target_home_win = None
    if include_target and home_final_score is not None and away_final_score is not None:
        target_home_win = int(home_final_score > away_final_score)

    starters = _starting_goalies(boxscore, home_abbrev, away_abbrev)
    return {
        "game_id": payload.get("id") or getattr(game_row, "game_id", None),
        "season": payload.get("season") or getattr(game_row, "season", None),
        "game_type": payload.get("gameType") or getattr(game_row, "game_type", None),
        "game_date": payload.get("gameDate") or getattr(game_row, "game_date", None),
        "start_time_utc": payload.get("startTimeUTC") or getattr(game_row, "start_time_utc", None),
        "venue": default_text(payload.get("venue")) or getattr(game_row, "venue", None),
        "game_state": payload.get("gameState") or getattr(game_row, "game_state", None),
        "home_team": home_abbrev,
        "away_team": away_abbrev,
        "home_team_id": home.get("id"),
        "away_team_id": away.get("id"),
        "team_id_to_side": {home.get("id"): "home", away.get("id"): "away"},
        "team_id_to_abbrev": {home.get("id"): home_abbrev, away.get("id"): away_abbrev},
        "home_final_score": home_final_score,
        "away_final_score": away_final_score,
        "target_home_win": target_home_win,
        "max_periods": int(payload.get("maxPeriods") or 5),
        "home_goalie_id": starters.get("home_goalie_id"),
        "away_goalie_id": starters.get("away_goalie_id"),
    }


def _initial_state(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "home_score": 0,
        "away_score": 0,
        "home_sog": 0,
        "away_sog": 0,
        "home_shot_attempts": 0,
        "away_shot_attempts": 0,
        "home_missed_shots": 0,
        "away_missed_shots": 0,
        "home_blocked_shots_for": 0,
        "away_blocked_shots_for": 0,
        "home_blocks": 0,
        "away_blocks": 0,
        "home_hits": 0,
        "away_hits": 0,
        "home_giveaways": 0,
        "away_giveaways": 0,
        "home_takeaways": 0,
        "away_takeaways": 0,
        "home_faceoff_wins": 0,
        "away_faceoff_wins": 0,
        "home_penalties": 0,
        "away_penalties": 0,
        "home_penalty_minutes": 0,
        "away_penalty_minutes": 0,
        "home_power_play_opportunities": 0,
        "away_power_play_opportunities": 0,
        "home_power_play_goals": 0,
        "away_power_play_goals": 0,
        "home_short_handed_goals": 0,
        "away_short_handed_goals": 0,
        "home_goalie_id": context.get("home_goalie_id"),
        "away_goalie_id": context.get("away_goalie_id"),
        "home_goalie_saves": 0,
        "away_goalie_saves": 0,
        "home_goalie_goals_against": 0,
        "away_goalie_goals_against": 0,
    }


def _apply_event_to_state(
    state: dict[str, Any],
    active_penalties: list[dict[str, Any]],
    context: dict[str, Any],
    play: dict[str, Any],
    details: dict[str, Any],
    event_type: str | None,
    event_team_side: str | None,
    seconds_elapsed: int | None,
) -> None:
    if event_type in SHOT_ATTEMPT_EVENTS and event_team_side:
        state[f"{event_team_side}_shot_attempts"] += 1
    if event_type == "missed-shot" and event_team_side:
        state[f"{event_team_side}_missed_shots"] += 1
    if event_type == BLOCKED_SHOT_EVENT and event_team_side:
        defending_side = _opponent(event_team_side)
        state[f"{event_team_side}_blocked_shots_for"] += 1
        state[f"{defending_side}_blocks"] += 1
    if event_type == "shot-on-goal":
        _record_shot_on_goal(state, context, details, event_team_side, goal=False)
    if event_type == GOAL_EVENT and event_team_side:
        _record_goal(state, active_penalties, context, play, details, event_team_side)
    if event_type == HIT_EVENT and event_team_side:
        state[f"{event_team_side}_hits"] += 1
    if event_type == GIVEAWAY_EVENT and event_team_side:
        state[f"{event_team_side}_giveaways"] += 1
    if event_type == TAKEAWAY_EVENT and event_team_side:
        state[f"{event_team_side}_takeaways"] += 1
    if event_type == FACEOFF_EVENT:
        winner_side = context["team_id_to_side"].get(details.get("eventOwnerTeamId"))
        if winner_side:
            state[f"{winner_side}_faceoff_wins"] += 1
    if event_type == PENALTY_EVENT and event_team_side:
        minutes = _number(details.get("duration")) or 0
        state[f"{event_team_side}_penalties"] += 1
        state[f"{event_team_side}_penalty_minutes"] += minutes
        if minutes > 0 and seconds_elapsed is not None:
            active_penalties.append(
                {
                    "team_side": event_team_side,
                    "starts_at": seconds_elapsed,
                    "expires_at": seconds_elapsed + int(minutes * 60),
                    "duration_seconds": int(minutes * 60),
                    "minor": minutes <= 2,
                }
            )


def _record_shot_on_goal(
    state: dict[str, Any],
    context: dict[str, Any],
    details: dict[str, Any],
    event_team_side: str | None,
    goal: bool,
) -> None:
    if not event_team_side:
        return
    state[f"{event_team_side}_sog"] += 1
    goalie_side = _opponent(event_team_side)
    goalie_id = details.get("goalieInNetId")
    if goalie_id:
        state[f"{goalie_side}_goalie_id"] = goalie_id
    if goal:
        state[f"{goalie_side}_goalie_goals_against"] += 1
    else:
        state[f"{goalie_side}_goalie_saves"] += 1


def _record_goal(
    state: dict[str, Any],
    active_penalties: list[dict[str, Any]],
    context: dict[str, Any],
    play: dict[str, Any],
    details: dict[str, Any],
    event_team_side: str,
) -> None:
    _record_shot_on_goal(state, context, details, event_team_side, goal=True)
    state[f"{event_team_side}_score"] = int(details.get(f"{event_team_side}Score") or state[f"{event_team_side}_score"] + 1)
    opponent_side = _opponent(event_team_side)
    if details.get(f"{opponent_side}Score") is not None:
        state[f"{opponent_side}_score"] = int(details[f"{opponent_side}Score"])

    situation = _parse_situation(play.get("situationCode"))
    if event_team_side == "home" and situation["home_skaters"] > situation["away_skaters"]:
        state["home_power_play_goals"] += 1
        _remove_oldest_minor(active_penalties, "away")
    elif event_team_side == "away" and situation["away_skaters"] > situation["home_skaters"]:
        state["away_power_play_goals"] += 1
        _remove_oldest_minor(active_penalties, "home")
    elif event_team_side == "home" and situation["home_skaters"] < situation["away_skaters"]:
        state["home_short_handed_goals"] += 1
    elif event_team_side == "away" and situation["away_skaters"] < situation["home_skaters"]:
        state["away_short_handed_goals"] += 1


def _base_row(
    context: dict[str, Any],
    state: dict[str, Any],
    active_penalties: list[dict[str, Any]],
    play: dict[str, Any],
    details: dict[str, Any],
    event_index: int,
    situation: dict[str, int],
) -> dict[str, Any]:
    period = (play.get("periodDescriptor") or {}).get("number")
    seconds_elapsed = _game_seconds(period, play.get("timeInPeriod"))
    seconds_remaining_game = _seconds_remaining_game(seconds_elapsed, context["max_periods"])
    active = _active_penalty_summary(active_penalties, seconds_elapsed)
    event_team = context["team_id_to_abbrev"].get(details.get("eventOwnerTeamId"))
    event_team_side = context["team_id_to_side"].get(details.get("eventOwnerTeamId"))
    home_goalie_shots = state["home_goalie_saves"] + state["home_goalie_goals_against"]
    away_goalie_shots = state["away_goalie_saves"] + state["away_goalie_goals_against"]

    return {
        "game_id": context["game_id"],
        "season": context["season"],
        "game_type": context["game_type"],
        "game_date": context["game_date"],
        "start_time_utc": context["start_time_utc"],
        "venue": context["venue"],
        "game_state": context["game_state"],
        "home_team": context["home_team"],
        "away_team": context["away_team"],
        "event_index": event_index,
        "event_id": play.get("eventId"),
        "sort_order": play.get("sortOrder"),
        "event_type": play.get("typeDescKey"),
        "event_team": event_team,
        "event_team_side": event_team_side,
        "period": period,
        "period_type": (play.get("periodDescriptor") or {}).get("periodType"),
        "time_in_period": play.get("timeInPeriod"),
        "time_remaining": play.get("timeRemaining"),
        "seconds_elapsed": seconds_elapsed,
        "seconds_remaining_regulation": max(0, 3600 - min(seconds_elapsed or 0, 3600)),
        "seconds_remaining_game": seconds_remaining_game,
        "game_progress": round((seconds_elapsed or 0) / ((context["max_periods"] - 3) * 300 + 3600), 5),
        "situation_code": play.get("situationCode"),
        "home_skaters": situation["home_skaters"],
        "away_skaters": situation["away_skaters"],
        "home_goalie_on_ice": situation["home_goalie_on_ice"],
        "away_goalie_on_ice": situation["away_goalie_on_ice"],
        "home_empty_net": int(situation["home_goalie_on_ice"] == 0),
        "away_empty_net": int(situation["away_goalie_on_ice"] == 0),
        "manpower_diff_home": situation["home_skaters"] - situation["away_skaters"],
        "home_power_play": int(situation["home_skaters"] > situation["away_skaters"]),
        "away_power_play": int(situation["away_skaters"] > situation["home_skaters"]),
        "even_strength": situation["even_strength"],
        "home_score": state["home_score"],
        "away_score": state["away_score"],
        "score_diff_home": state["home_score"] - state["away_score"],
        "abs_score_diff": abs(state["home_score"] - state["away_score"]),
        "home_sog": state["home_sog"],
        "away_sog": state["away_sog"],
        "sog_diff_home": state["home_sog"] - state["away_sog"],
        "home_shot_attempts": state["home_shot_attempts"],
        "away_shot_attempts": state["away_shot_attempts"],
        "shot_attempt_diff_home": state["home_shot_attempts"] - state["away_shot_attempts"],
        "home_missed_shots": state["home_missed_shots"],
        "away_missed_shots": state["away_missed_shots"],
        "home_blocked_shots_for": state["home_blocked_shots_for"],
        "away_blocked_shots_for": state["away_blocked_shots_for"],
        "home_blocks": state["home_blocks"],
        "away_blocks": state["away_blocks"],
        "home_hits": state["home_hits"],
        "away_hits": state["away_hits"],
        "hit_diff_home": state["home_hits"] - state["away_hits"],
        "home_giveaways": state["home_giveaways"],
        "away_giveaways": state["away_giveaways"],
        "home_takeaways": state["home_takeaways"],
        "away_takeaways": state["away_takeaways"],
        "home_faceoff_wins": state["home_faceoff_wins"],
        "away_faceoff_wins": state["away_faceoff_wins"],
        "faceoff_win_diff_home": state["home_faceoff_wins"] - state["away_faceoff_wins"],
        "home_penalties": state["home_penalties"],
        "away_penalties": state["away_penalties"],
        "home_penalty_minutes": state["home_penalty_minutes"],
        "away_penalty_minutes": state["away_penalty_minutes"],
        "penalty_minute_diff_home": state["home_penalty_minutes"] - state["away_penalty_minutes"],
        "home_active_penalties": active["home_count"],
        "away_active_penalties": active["away_count"],
        "home_active_penalty_seconds": active["home_seconds"],
        "away_active_penalty_seconds": active["away_seconds"],
        "home_power_play_opportunities": state["home_power_play_opportunities"],
        "away_power_play_opportunities": state["away_power_play_opportunities"],
        "home_power_play_goals": state["home_power_play_goals"],
        "away_power_play_goals": state["away_power_play_goals"],
        "home_short_handed_goals": state["home_short_handed_goals"],
        "away_short_handed_goals": state["away_short_handed_goals"],
        "home_goalie_id": state["home_goalie_id"],
        "away_goalie_id": state["away_goalie_id"],
        "home_goalie_saves": state["home_goalie_saves"],
        "away_goalie_saves": state["away_goalie_saves"],
        "home_goalie_goals_against": state["home_goalie_goals_against"],
        "away_goalie_goals_against": state["away_goalie_goals_against"],
        "home_goalie_save_pct_live": round(state["home_goalie_saves"] / home_goalie_shots, 4)
        if home_goalie_shots
        else None,
        "away_goalie_save_pct_live": round(state["away_goalie_saves"] / away_goalie_shots, 4)
        if away_goalie_shots
        else None,
        "x_coord": details.get("xCoord"),
        "y_coord": details.get("yCoord"),
        "zone_code": details.get("zoneCode"),
        "shot_type": details.get("shotType"),
        "penalty_type": details.get("typeCode"),
        "penalty_minutes_event": details.get("duration"),
        "reason": details.get("reason") or details.get("secondaryReason") or details.get("descKey"),
        "shooting_player_id": details.get("shootingPlayerId"),
        "scoring_player_id": details.get("scoringPlayerId"),
        "goalie_in_net_id": details.get("goalieInNetId"),
        "committed_by_player_id": details.get("committedByPlayerId"),
        "drawn_by_player_id": details.get("drawnByPlayerId"),
        "home_final_score": context["home_final_score"],
        "away_final_score": context["away_final_score"],
        "target_home_win": context["target_home_win"],
    }


def _starting_goalies(boxscore: dict[str, Any] | None, home_team: str | None, away_team: str | None) -> dict[str, Any]:
    if not boxscore:
        return {}
    starters: dict[str, Any] = {}
    for side in ("home", "away"):
        groups = (boxscore.get("playerByGameStats") or {}).get(f"{side}Team", {})
        goalies = groups.get("goalies", []) or []
        if not goalies:
            continue
        starter = max(goalies, key=lambda goalie: _time_to_seconds(goalie.get("toi")) or 0)
        starters[f"{side}_goalie_id"] = starter.get("playerId")
    return starters


def _parse_situation(value: Any) -> dict[str, int]:
    code = str(value or "1551").zfill(4)
    try:
        away_goalie = int(code[0])
        away_skaters = int(code[1])
        home_skaters = int(code[2])
        home_goalie = int(code[3])
    except ValueError:
        away_goalie, away_skaters, home_skaters, home_goalie = 1, 5, 5, 1
    return {
        "home_skaters": home_skaters,
        "away_skaters": away_skaters,
        "home_goalie_on_ice": home_goalie,
        "away_goalie_on_ice": away_goalie,
        "even_strength": int(home_skaters == away_skaters),
    }


def _power_play_side(situation: dict[str, int]) -> str | None:
    if situation["home_skaters"] > situation["away_skaters"]:
        return "home"
    if situation["away_skaters"] > situation["home_skaters"]:
        return "away"
    return None


def _expire_penalties(active_penalties: list[dict[str, Any]], seconds_elapsed: int | None) -> None:
    if seconds_elapsed is None:
        return
    active_penalties[:] = [penalty for penalty in active_penalties if penalty["expires_at"] > seconds_elapsed]


def _remove_oldest_minor(active_penalties: list[dict[str, Any]], team_side: str) -> None:
    for index, penalty in enumerate(active_penalties):
        if penalty["team_side"] == team_side and penalty.get("minor"):
            del active_penalties[index]
            return


def _active_penalty_summary(active_penalties: list[dict[str, Any]], seconds_elapsed: int | None) -> dict[str, int]:
    summary = {"home_count": 0, "away_count": 0, "home_seconds": 0, "away_seconds": 0}
    now = seconds_elapsed or 0
    for penalty in active_penalties:
        side = penalty["team_side"]
        remaining = max(0, int(penalty["expires_at"] - now))
        summary[f"{side}_count"] += 1
        summary[f"{side}_seconds"] += remaining
    return summary


def _opponent(side: str) -> str:
    return "away" if side == "home" else "home"


def _game_seconds(period: Any, period_time: Any) -> int | None:
    elapsed = _time_to_seconds(period_time)
    if elapsed is None or period is None:
        return None
    period_number = int(period)
    if period_number <= 0:
        return 0
    if period_number <= 3:
        return (period_number - 1) * 1200 + elapsed
    return 3600 + (period_number - 4) * 300 + elapsed


def _seconds_remaining_game(seconds_elapsed: int | None, max_periods: int) -> int | None:
    if seconds_elapsed is None:
        return None
    total_seconds = 3600 + max(0, max_periods - 3) * 300
    return max(0, total_seconds - seconds_elapsed)


def _time_to_seconds(value: Any) -> int | None:
    if not value or ":" not in str(value):
        return None
    minutes, seconds = str(value).split(":", 1)
    try:
        return int(minutes) * 60 + int(seconds)
    except ValueError:
        return None


def _number(*values: Any) -> float | None:
    for value in values:
        if value is not None and not pd.isna(value):
            return float(value)
    return None


def _read_optional(path: Path) -> Any | None:
    return read_json(path) if path.exists() else None
