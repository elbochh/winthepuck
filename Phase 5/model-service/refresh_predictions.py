"""Work out the model's predictions for the next NHL games and send them to the website.

This is the light job that runs in the cloud once a day (GitHub Actions):

  1. Ask the free NHL API which games have been played and which are coming up.
  2. Move every team's Elo rating and recent-form numbers forward with the
     real results.
  3. Run the trained model from `serving/` over the upcoming games.
  4. Send the predictions, the finished scores and the league table to the
     Flask website running on Azure.

Nothing is re-trained here, so the whole job finishes in about a minute.

    python3 refresh_predictions.py --out refresh_payload.json
    python3 refresh_predictions.py --post https://<site>.azurewebsites.net --token <token>
"""
from __future__ import annotations

import argparse
import json
import math
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np

import elo
import nhl_api
from form_book import FormBook, last_five_form

HERE = Path(__file__).resolve().parent
SERVING = HERE / "serving"

# Preseason games (type 1) are ignored: the model was never trained on them
# and half the players on the ice will be in the minor leagues by October.
COUNTED_GAME_TYPES = {2, 3}

# In the off-season, how many days of the new season to predict once we find it.
OFFSEASON_EXTRA_DAYS = 5

# A playoff game has extra inputs about the series. For a regular season game
# they are all zero, which is exactly what the model was trained on.
REGULAR_SEASON_PLAYOFF_COLUMNS = {
    "playoff_series_game_number": 0.0,
    "home_series_wins_before": 0.0,
    "away_series_wins_before": 0.0,
    "series_win_diff_before": 0.0,
    "home_elimination_game": 0.0,
    "away_elimination_game": 0.0,
}


# ===========================================================
# 1) LOADING WHAT THE MODEL NEEDS
# ===========================================================

def load_bundle() -> tuple[dict, list[str]]:
    bundle = joblib.load(SERVING / "pregame_model.joblib")
    return bundle["models"], bundle["feature_cols"]


def load_state() -> dict:
    return json.loads((SERVING / "team_state.json").read_text())


def season_id(day: date) -> int:
    """NHL seasons run across two years, so 2026-27 is written 20262027."""
    year = day.year if day.month >= 8 else day.year - 1
    return int(f"{year}{year + 1}")


# ===========================================================
# 2) CATCHING THE RATINGS UP WITH REAL RESULTS
# ===========================================================

def collect_games(seasons: list[int]) -> list[dict]:
    games: list[dict] = []
    for season in seasons:
        print(f"fetching schedule and results for season {season} ...")
        games.extend(nhl_api.all_games(season))
    games = [g for g in games if g["game_type"] in COUNTED_GAME_TYPES]
    games.sort(key=lambda g: (g["game_date"], g["game_id"]))
    print(f"  {len(games)} games, "
          f"{sum(1 for g in games if g['finished'])} of them finished")
    return games


def replay(states: dict[str, elo.TeamState], games: list[dict],
           known_until: date) -> int:
    """Update the Elo ratings with every finished game we have not seen yet."""
    applied = 0
    for game in games:
        played_on = nhl_api.parse_date(game["game_date"])
        if not game["finished"] or played_on <= known_until:
            continue
        home, away = game["home_team"], game["away_team"]
        for team in (home, away):
            states.setdefault(team, elo.TeamState(season=game["season"]))
            elo.start_new_season(states[team], game["season"])
        elo.apply_result(states[home], states[away],
                         int(game["home_score"]), int(game["away_score"]),
                         game["game_type"])
        applied += 1
    return applied


def prepare_for_season(states: dict[str, elo.TeamState], season: int) -> None:
    """Apply the summer reset to any team that has not played yet this season."""
    for state in states.values():
        elo.start_new_season(state, season)


# ===========================================================
# 3) BUILDING THE INPUT ROW FOR ONE UPCOMING GAME
# ===========================================================

def build_row(home_state: elo.TeamState, away_state: elo.TeamState,
              home_form: dict, away_form: dict, h2h: dict,
              feature_cols: list[str], season_game_index: int) -> dict[str, float]:
    """Put together the ~127 numbers the trained model expects for one game."""
    row: dict[str, float] = {}

    for side, state, live in (("home", home_state, home_form),
                              ("away", away_state, away_form)):
        # box-score numbers we cannot refresh without the big pipeline
        for name, value in state.features.items():
            row[f"{side}_{name}"] = value
        # everything the real scores can tell us, calculated fresh today
        for name, value in live.items():
            row[f"{side}_{name}"] = value

    row.update(elo.matchup_features(home_state, away_state))
    row.update(REGULAR_SEASON_PLAYOFF_COLUMNS)
    row.update({k: v for k, v in h2h.items() if v is not None})
    row["is_playoff"] = 0.0
    row["season_game_index"] = float(season_game_index)

    # Most inputs are stored a second time as a home-minus-away difference.
    for column in feature_cols:
        if column.endswith("_diff") and column not in row:
            base = column[: -len("_diff")]
            home_col, away_col = f"home_{base}", f"away_{base}"
            if home_col in row and away_col in row:
                row[column] = row[home_col] - row[away_col]

    # two differences the pipeline builds out of opposite splits
    if {"home_home_win_pct_before_game", "away_road_win_pct_before_game"} <= row.keys():
        row["home_ice_split_win_pct_diff"] = (
            row["home_home_win_pct_before_game"] - row["away_road_win_pct_before_game"])
    if {"home_home_goal_diff_avg_before_game",
            "away_road_goal_diff_avg_before_game"} <= row.keys():
        row["home_ice_split_goal_diff_avg_diff"] = (
            row["home_home_goal_diff_avg_before_game"]
            - row["away_road_goal_diff_avg_before_game"])
    return row


def predict(models: dict, feature_cols: list[str],
            rows: list[dict[str, float]]) -> np.ndarray:
    """Average the three trained models, the same way Phase 2 tested them."""
    matrix = np.array(
        [[float(row.get(column, np.nan)) for column in feature_cols] for row in rows],
        dtype=float,
    )
    probabilities = [model.predict_proba(matrix)[:, 1] for model in models.values()]
    return np.mean(probabilities, axis=0)


def fair_odds(probability: float) -> int:
    """American odds that match the model exactly, with no bookmaker margin."""
    probability = min(max(probability, 0.02), 0.98)
    if probability >= 0.5:
        return int(round(-100 * probability / (1 - probability)))
    return int(round(100 * (1 - probability) / probability))


# ===========================================================
# 4) THE LEAGUE TABLE SHOWN ON THE WEBSITE
# ===========================================================

def standings_end(season: int) -> date:
    payload = nhl_api.get_json(f"{nhl_api.WEB_API}/standings-season")
    for row in payload.get("seasons", []):
        if int(row["id"]) == season:
            return min(nhl_api.parse_date(row["standingsEnd"]), date.today())
    return date.today()


def team_table(games: list[dict], book: FormBook, season: int,
               states: dict[str, elo.TeamState]) -> list[dict]:
    """Records, season stats and last-five form for all 32 clubs."""
    played = sum(1 for g in games
                 if g["finished"] and g["season"] == season and g["game_type"] == 2)
    # In the summer, and for the first couple of weeks of a new season, the new
    # table is basically empty - so we keep showing last season's records.
    shown_season = season if played >= 64 else season - 10001
    if shown_season != season:
        print(f"season {season} has {played} finished games so far - "
              f"showing {shown_season} records for now")

    table = nhl_api.standings(standings_end(shown_season))
    stats = nhl_api.club_stats(shown_season)
    form = last_five_form(book, shown_season)

    details: dict[str, dict] = {}
    for game in games:
        details.setdefault(game["home_team"], {
            "city": game["home_city"], "name": game["home_name"],
            "logo": game["home_logo"]})
        details.setdefault(game["away_team"], {
            "city": game["away_city"], "name": game["away_name"],
            "logo": game["away_logo"]})

    rows = []
    for entry in table:
        abbr = entry["teamAbbrev"]["default"]
        base = details.get(abbr, {})
        full_name = entry["teamName"]["default"]
        state = states.get(abbr)
        rows.append({
            "abbr": abbr,
            "city": base.get("city") or " ".join(full_name.split()[:-1]),
            "name": base.get("name") or full_name.split()[-1],
            "logo": base.get("logo", ""),
            "record": f"{int(entry['wins'])}-{int(entry['losses'])}-{int(entry['otLosses'])}",
            "points": int(entry["points"]),
            "pointsPct": round(float(entry["pointPctg"]), 3),
            "gamesPlayed": int(entry["gamesPlayed"]),
            "streak": f"{entry.get('streakCode', '')}{int(entry.get('streakCount', 0) or 0)}",
            "form": form.get(abbr, []),
            "elo": round(state.elo, 1) if state else None,
            "stats": stats.get(abbr, {}),
            "statsSeason": shown_season,
        })
    rows.sort(key=lambda r: -r["points"])
    return rows


# ===========================================================
# 5) PUTTING IT ALL TOGETHER
# ===========================================================

def build_payload(days_ahead: int, history_days: int) -> dict:
    models, feature_cols = load_bundle()
    state = load_state()
    states = {team: elo.TeamState.from_dict(data)
              for team, data in state["teams"].items()}

    today = date.today()
    known_until = nhl_api.parse_date(state["asOfDate"])
    horizon = today + timedelta(days=days_ahead)
    seasons = sorted({state["season"], season_id(today), season_id(horizon)})
    seasons = [s for s in seasons if s >= state["season"]]

    games = collect_games(seasons)
    caught_up = replay(states, games, known_until)
    print(f"caught up on {caught_up} finished games since {known_until}")

    book = FormBook()
    for game in games:
        book.add(game)
    book.sort()

    current_season = max(s for s in seasons if s <= season_id(horizon))
    prepare_for_season(states, current_season)
    played_this_season = sum(
        1 for g in games if g["finished"] and g["season"] == current_season)

    scheduled = [g for g in games
                 if not g["finished"] and nhl_api.parse_date(g["game_date"]) >= today]
    wanted = [g for g in scheduled
              if nhl_api.parse_date(g["game_date"]) <= horizon]

    # Between seasons the next game can be months away, and a website with an
    # empty schedule page looks broken. If the normal window is empty, reach
    # further ahead and take the first slate of the new season instead.
    if not wanted and scheduled:
        first_day = nhl_api.parse_date(scheduled[0]["game_date"])
        stretch = first_day + timedelta(days=OFFSEASON_EXTRA_DAYS)
        wanted = [g for g in scheduled
                  if nhl_api.parse_date(g["game_date"]) <= stretch]
        print(f"nothing scheduled before {horizon}; the next games are on "
              f"{first_day}, so predicting {len(wanted)} of them instead")

    rows, meta = [], []
    for game in wanted:
        game_day = nhl_api.parse_date(game["game_date"])
        home, away = game["home_team"], game["away_team"]
        if home not in states or away not in states:
            continue
        rows.append(build_row(
            states[home], states[away],
            book.team_features(home, game_day, game["season"]),
            book.team_features(away, game_day, game["season"]),
            book.head_to_head(home, away, game_day),
            feature_cols,
            season_game_index=played_this_season,
        ))
        meta.append(game)

    probabilities = predict(models, feature_cols, rows) if rows else []
    upcoming = []
    for game, probability in zip(meta, probabilities):
        probability = float(probability)
        if math.isnan(probability):
            continue
        upcoming.append({
            "gameId": game["game_id"],
            "gameDate": game["game_date"],
            "startTimeUtc": game["start_time_utc"],
            "venue": game["venue"],
            "home": game["home_team"],
            "away": game["away_team"],
            "homeWinProb": round(100 * probability, 1),
            "confidence": round(100 * max(probability, 1 - probability), 1),
            "homeOdds": fair_odds(probability),
            "awayOdds": fair_odds(1 - probability),
            "pick": game["home_team"] if probability >= 0.5 else game["away_team"],
        })

    since = today - timedelta(days=history_days)
    finished = [
        {
            "gameId": g["game_id"],
            "gameDate": g["game_date"],
            "home": g["home_team"], "away": g["away_team"],
            "homeScore": int(g["home_score"]), "awayScore": int(g["away_score"]),
            "winner": (g["home_team"] if g["home_score"] > g["away_score"]
                       else g["away_team"]),
            "overtime": g["last_period_type"] in {"OT", "SO"},
        }
        for g in games
        if g["finished"] and nhl_api.parse_date(g["game_date"]) >= since
    ]

    report_path = SERVING / "model_report.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": current_season,
        "modelTrainedTo": state["asOfDate"],
        "teams": team_table(games, book, current_season, states),
        "upcoming": upcoming,
        "finished": finished,
        "modelReport": report,
    }


def post_payload(base_url: str, token: str, payload: dict) -> None:
    url = base_url.rstrip("/") + "/api/admin/refresh"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        print(f"website replied {response.status}: {response.read().decode()[:400]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days-ahead", type=int, default=14,
                        help="how far into the future to predict")
    parser.add_argument("--history-days", type=int, default=21,
                        help="how far back to send finished scores")
    parser.add_argument("--out", default="refresh_payload.json")
    parser.add_argument("--post", default=None, help="website address to send to")
    parser.add_argument("--token", default=None, help="the website's refresh token")
    args = parser.parse_args()

    payload = build_payload(args.days_ahead, args.history_days)
    Path(args.out).write_text(json.dumps(payload, indent=1))
    print(f"\n{len(payload['upcoming'])} upcoming predictions, "
          f"{len(payload['finished'])} finished games, "
          f"{len(payload['teams'])} teams -> {args.out}")

    if args.post:
        if not args.token:
            raise SystemExit("--post needs --token as well")
        post_payload(args.post, args.token, payload)


if __name__ == "__main__":
    main()
