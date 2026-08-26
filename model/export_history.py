"""Export the real games and real predictions the website starts life with.

Run on a laptop, next to the training output. It writes two small files
into `serving/` that get committed to GitHub and loaded into the cloud
database the first time the site starts:

  season_history.json  every game of the last completed season with the
                       probability the model gave it *before* it was played
                       (taken straight from the walk-forward test, so none of
                       these numbers were fitted on the result they predict)
  live_replay.json     one real playoff game, event by event, run through the
                       live win-probability model

    python3 export_history.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ML_DIR = HERE.parent / "ml"
WEBSITE_DATA = HERE.parent / "frontend" / "data"
OUT = HERE / "serving"

SEASON = 20252026
SEASON_LABEL = "2025-26"


def export_season_history() -> None:
    walk_forward = pd.read_csv(ML_DIR / "data" / "walkforward_predictions.csv",
                               parse_dates=["game_date"])
    dataset = pd.read_csv(ML_DIR / "data" / "model_dataset.csv",
                          usecols=["game_id", "home_team", "away_team",
                                   "home_score", "away_score"])

    season = walk_forward[walk_forward["season"] == SEASON].copy()
    season = season.merge(dataset, on="game_id", how="inner")
    season = season.sort_values("game_date").reset_index(drop=True)

    season["picked_home"] = season["p_home"] >= 0.5
    season["correct"] = season["picked_home"].astype(int) == season["y"]

    games = [
        {
            "gameId": int(row.game_id),
            "gameDate": row.game_date.strftime("%Y-%m-%d"),
            "home": row.home_team,
            "away": row.away_team,
            "homeScore": int(row.home_score),
            "awayScore": int(row.away_score),
            "homeWinProb": round(100 * float(row.p_home), 1),
            "confidence": round(100 * max(float(row.p_home), 1 - float(row.p_home)), 1),
            "pick": row.home_team if row.picked_home else row.away_team,
            "winner": row.home_team if row.y == 1 else row.away_team,
            "correct": bool(row.correct),
            "playoff": int(row.game_type) == 3,
        }
        for row in season.itertuples(index=False)
    ]

    confidence = np.maximum(season["p_home"], 1 - season["p_home"])
    confident = season[confidence >= 0.60]
    monthly = [
        {"month": month, "games": int(len(group)),
         "accuracy": round(100 * group["correct"].mean(), 1)}
        for month, group in season.groupby(season["game_date"].dt.strftime("%Y-%m"))
    ]

    payload = {
        "season": SEASON,
        "label": SEASON_LABEL,
        "summary": {
            "games": len(games),
            "accuracy": round(100 * season["correct"].mean(), 1),
            "confidentGames": int(len(confident)),
            "confidentAccuracy": round(100 * confident["correct"].mean(), 1),
            "correctPicks": int(season["correct"].sum()),
        },
        "monthly": monthly,
        "games": games,
    }
    (OUT / "season_history.json").write_text(json.dumps(payload, indent=1))
    print(f"season_history.json: {len(games)} real games from {SEASON_LABEL}, "
          f"model accuracy {payload['summary']['accuracy']}%")


def export_live_replay() -> None:
    """The event-by-event win probability of one real playoff game."""
    source = WEBSITE_DATA / "live_demo.json"
    if not source.exists():
        print("live_demo.json not found - run ml/export_site_data.py first")
        return
    payload = json.loads(source.read_text())
    shutil.copyfile(source, OUT / "live_replay.json")
    print(f"live_replay.json: {payload['away']} {payload['finalAway']} - "
          f"{payload['finalHome']} {payload['home']} on {payload['date']}, "
          f"{len(payload['timeline'])} events")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    export_season_history()
    export_live_replay()


if __name__ == "__main__":
    main()
