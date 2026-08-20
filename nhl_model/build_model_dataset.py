"""Build the final modeling dataset: merged_model_data.csv + Elo ratings + decay features.

Elo design follows FiveThirtyEight's NHL Elo:
  - K = 6, home-ice advantage = 50 Elo points
  - margin-of-victory multiplier: 0.6686 * ln(|goal_diff|) + 0.8048,
    scaled by an autocorrelation term so favorites don't inflate
  - between seasons each team reverts 30% toward the league mean (1505)

Outputs data/model_dataset.csv (one row per completed game, chronological).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

PIPELINE_DIR = Path(__file__).resolve().parent.parent / "nhl_data_pipeline"
MERGED_PATH = PIPELINE_DIR / "data" / "processed" / "merged_model_data.csv"
OUT_DIR = Path(__file__).resolve().parent / "data"

MEAN_ELO = 1505.0
K = 6.0
HFA = 50.0  # home-ice advantage in Elo points
SEASON_REVERSION = 0.30
PLAYOFF_MULT = 1.25  # playoff games move ratings a bit more


def elo_win_prob(elo_diff: float) -> float:
    return 1.0 / (10.0 ** (-elo_diff / 400.0) + 1.0)


def mov_multiplier(goal_diff: int, elo_diff_winner: float) -> float:
    """FiveThirtyEight NHL margin-of-victory multiplier with autocorrelation term."""
    mult = 0.6686 * math.log(max(abs(goal_diff), 1)) + 0.8048
    return mult * (2.05 / (elo_diff_winner * 0.001 + 2.05))


def build() -> pd.DataFrame:
    df = pd.read_csv(MERGED_PATH)
    df = df[df["target_home_win"].notna()].copy()
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    elo: dict[str, float] = {}
    last_season: dict[str, int] = {}
    # exponentially decayed goal differential per team (long-memory form signal)
    decay_gd: dict[str, float] = {}
    decay_win: dict[str, float] = {}
    ALPHA = 0.05  # decay rate per game

    rows = []
    for game in df.itertuples(index=False):
        home, away, season = game.home_team, game.away_team, int(game.season)
        for team in (home, away):
            if team not in elo:
                elo[team] = MEAN_ELO
                decay_gd[team] = 0.0
                decay_win[team] = 0.5
                last_season[team] = season
            elif last_season[team] != season:
                elo[team] = MEAN_ELO + (elo[team] - MEAN_ELO) * (1 - SEASON_REVERSION)
                decay_gd[team] *= 0.5
                decay_win[team] = 0.5 + (decay_win[team] - 0.5) * 0.5
                last_season[team] = season

        home_elo, away_elo = elo[home], elo[away]
        elo_diff = home_elo + HFA - away_elo
        p_home = elo_win_prob(elo_diff)

        rows.append(
            {
                "game_id": game.game_id,
                "home_elo_pre": home_elo,
                "away_elo_pre": away_elo,
                "elo_diff": home_elo - away_elo,
                "elo_prob_home": p_home,
                "home_decay_goal_diff": decay_gd[home],
                "away_decay_goal_diff": decay_gd[away],
                "home_decay_win_rate": decay_win[home],
                "away_decay_win_rate": decay_win[away],
                "decay_goal_diff_diff": decay_gd[home] - decay_gd[away],
                "decay_win_rate_diff": decay_win[home] - decay_win[away],
            }
        )

        # update ratings with the observed result
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

    elo_df = pd.DataFrame(rows)
    out = df.merge(elo_df, on="game_id", validate="one_to_one")

    # simple schedule-position feature
    out["season_game_index"] = out.groupby("season").cumcount()
    out["is_playoff"] = (out["game_type"] == 3).astype(int)

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "model_dataset.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}: {out.shape[0]} games, {out.shape[1]} columns")
    print(f"Elo-only accuracy (pick side with p>=0.5): "
          f"{((out['elo_prob_home'] >= 0.5) == (out['target_home_win'] == 1)).mean():.4f}")
    return out


if __name__ == "__main__":
    build()
