"""Predict winners for upcoming games.

Trains the ensemble on ALL completed games in data/model_dataset.csv, then
builds pre-game features for each row of the pipeline's upcoming_games.csv
(current Elo/decay state + each team's latest rolling features) and writes
data/upcoming_predictions.csv with home win probability and the pick.

Run after refreshing the data pipeline:
  cd ../nhl_data_pipeline && python main.py --mode upcoming && python main.py --mode build-merged
  cd ../nhl_model && python3 build_model_dataset.py && python3 predict_upcoming.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from build_model_dataset import (
    HFA, K, MEAN_ELO, PLAYOFF_MULT, SEASON_REVERSION,
    MERGED_PATH, elo_win_prob, mov_multiplier,
)
from train_evaluate import DATA_PATH, load_dataset, make_models

PIPELINE_DIR = Path(__file__).resolve().parent.parent / "nhl_data_pipeline"
UPCOMING_PATH = PIPELINE_DIR / "data" / "processed" / "upcoming_games.csv"
OUT_PATH = Path(__file__).resolve().parent / "data" / "upcoming_predictions.csv"


def current_team_state(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Replay dataset chronologically to recover each team's current Elo/decay state."""
    import math
    elo: dict[str, float] = {}
    decay_gd: dict[str, float] = {}
    decay_win: dict[str, float] = {}
    last_season: dict[str, int] = {}
    ALPHA = 0.05
    for game in df.sort_values(["game_date", "game_id"]).itertuples(index=False):
        home, away, season = game.home_team, game.away_team, int(game.season)
        for team in (home, away):
            if team not in elo:
                elo[team], decay_gd[team], decay_win[team] = MEAN_ELO, 0.0, 0.5
                last_season[team] = season
            elif last_season[team] != season:
                elo[team] = MEAN_ELO + (elo[team] - MEAN_ELO) * (1 - SEASON_REVERSION)
                decay_gd[team] *= 0.5
                decay_win[team] = 0.5 + (decay_win[team] - 0.5) * 0.5
                last_season[team] = season
        elo_diff = elo[home] + HFA - elo[away]
        p_home = elo_win_prob(elo_diff)
        home_win = int(game.target_home_win)
        goal_diff = int(game.home_score) - int(game.away_score)
        winner_elo_diff = elo_diff if home_win else -elo_diff
        k = K * (PLAYOFF_MULT if int(game.game_type) == 3 else 1.0)
        shift = k * mov_multiplier(goal_diff, winner_elo_diff) * (home_win - p_home)
        elo[home] += shift
        elo[away] -= shift
        decay_gd[home] = (1 - ALPHA) * decay_gd[home] + ALPHA * goal_diff
        decay_gd[away] = (1 - ALPHA) * decay_gd[away] - ALPHA * goal_diff
        decay_win[home] = (1 - ALPHA) * decay_win[home] + ALPHA * home_win
        decay_win[away] = (1 - ALPHA) * decay_win[away] + ALPHA * (1 - home_win)
    return {
        t: {"elo": elo[t], "decay_gd": decay_gd[t], "decay_win": decay_win[t]}
        for t in elo
    }


def latest_team_features(df: pd.DataFrame, team: str, prefix: str) -> dict[str, float]:
    """Take the team's most recent pre-game rolling features from its last game row."""
    home_games = df[df["home_team"] == team]
    away_games = df[df["away_team"] == team]
    last_home = home_games.iloc[-1] if len(home_games) else None
    last_away = away_games.iloc[-1] if len(away_games) else None
    if last_home is None and last_away is None:
        return {}
    if last_away is None or (last_home is not None and last_home.game_date >= last_away.game_date):
        row, side = last_home, "home"
    else:
        row, side = last_away, "away"
    feats = {}
    for col in df.columns:
        if col.startswith(f"{side}_") and pd.api.types.is_numeric_dtype(df[col]):
            feats[prefix + col[len(side) + 1:]] = row[col]
    return feats


def main() -> None:
    df, feature_cols = load_dataset()
    upcoming = pd.read_csv(UPCOMING_PATH)
    if upcoming.empty:
        print("No upcoming games.")
        return

    state = current_team_state(df)
    rows = []
    for g in upcoming.itertuples(index=False):
        home, away = g.home_team, g.away_team
        if home not in state or away not in state:
            print(f"skip {away} @ {home}: unknown team")
            continue
        # build home_/away_ prefixed features from each team's latest game
        hf = latest_team_features(df, home, "home_")
        af = latest_team_features(df, away, "away_")
        feats = {**hf, **af}
        hs, as_ = state[home], state[away]
        feats.update({
            "home_elo_pre": hs["elo"], "away_elo_pre": as_["elo"],
            "elo_diff": hs["elo"] - as_["elo"],
            "elo_prob_home": elo_win_prob(hs["elo"] + HFA - as_["elo"]),
            "home_decay_goal_diff": hs["decay_gd"], "away_decay_goal_diff": as_["decay_gd"],
            "home_decay_win_rate": hs["decay_win"], "away_decay_win_rate": as_["decay_win"],
            "decay_goal_diff_diff": hs["decay_gd"] - as_["decay_gd"],
            "decay_win_rate_diff": hs["decay_win"] - as_["decay_win"],
            "is_playoff": 0, "season_game_index": df["season_game_index"].max(),
        })
        # recompute diff columns where both sides exist
        for col in feature_cols:
            if col.endswith("_diff") and col not in feats:
                h_col, a_col = "home_" + col[:-5], "away_" + col[:-5]
                if h_col in feats and a_col in feats:
                    feats[col] = feats[h_col] - feats[a_col]
        rows.append({"home_team": home, "away_team": away,
                     "game_date": getattr(g, "game_date", ""), **feats})

    if not rows:
        print("No predictable games.")
        return
    Xup = pd.DataFrame(rows)
    for col in feature_cols:
        if col not in Xup.columns:
            Xup[col] = np.nan

    y = df["target_home_win"].astype(int).to_numpy()
    X = df[feature_cols].to_numpy(dtype=float)
    probs = []
    for name, model in make_models().items():
        model.fit(X, y)
        probs.append(model.predict_proba(Xup[feature_cols].to_numpy(dtype=float))[:, 1])
    Xup["p_home_win"] = np.mean(probs, axis=0)
    Xup["pick"] = np.where(Xup["p_home_win"] >= 0.5, Xup["home_team"], Xup["away_team"])
    Xup["confidence"] = np.maximum(Xup["p_home_win"], 1 - Xup["p_home_win"])

    out = Xup[["game_date", "away_team", "home_team", "p_home_win", "pick", "confidence"]]
    out.to_csv(OUT_PATH, index=False)
    print(out.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
