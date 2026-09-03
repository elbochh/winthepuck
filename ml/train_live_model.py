"""Second-stage in-game win-probability model.

Stacks on the pregame model: for every play-by-play event of a game it takes
  - the pregame ensemble probability (out-of-sample, from walk-forward preds)
  - live game state: score, clock, manpower, shots, penalties, goalie form...
and outputs P(home wins | state now).

Design notes (research-grounded):
  - Score diff x time remaining is the dominant signal (all published in-game
    models: score effects + time transforms). We add score_diff scaled by
    1/sqrt(time remaining), the classic "goals matter more late" transform.
  - The pregame prior should dominate at t=0 and wash out by t=end; the model
    learns this blend itself from data.
  - Train: 2022-23 .. 2024-25 events. Test: all 2025-26 events (unseen season).
  - Model: HistGradientBoosting (monotone in score_diff), isotonic-calibrated.

Outputs: models/live_model.joblib + printed evaluation by game phase.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

HERE = Path(__file__).resolve().parent
PIPELINE_DIR = HERE.parent / "pipeline"
LIVE_PATH = PIPELINE_DIR / "data" / "processed" / "live_win_probability_features.csv"
WALKFWD_PATH = HERE / "data" / "walkforward_predictions.csv"
MODEL_DIR = HERE / "models"

LIVE_FEATURES = [
    # clock / phase
    "period", "seconds_remaining_regulation", "seconds_remaining_game", "game_progress",
    # score
    "score_diff_home", "abs_score_diff", "home_score", "away_score",
    # scaled score (goals matter more late)
    "score_diff_per_sqrt_time",
    # shots / possession proxies
    "sog_diff_home", "shot_attempt_diff_home", "home_sog", "away_sog",
    # manpower / special teams
    "manpower_diff_home", "home_power_play", "away_power_play", "even_strength",
    "home_active_penalty_seconds", "away_active_penalty_seconds",
    "home_empty_net", "away_empty_net",
    "home_power_play_opportunities", "away_power_play_opportunities",
    "home_power_play_goals", "away_power_play_goals",
    # physical / possession events
    "faceoff_win_diff_home", "hit_diff_home",
    "home_takeaways", "away_takeaways", "home_giveaways", "away_giveaways",
    # live goalie performance
    "home_goalie_save_pct_live", "away_goalie_save_pct_live",
    "home_goalie_saves", "away_goalie_saves",
    # pregame prior
    "pregame_home_prob",
    "is_playoff",
]

USECOLS = [
    "game_id", "season", "game_type", "event_index",
    "period", "seconds_remaining_regulation", "seconds_remaining_game", "game_progress",
    "score_diff_home", "abs_score_diff", "home_score", "away_score",
    "sog_diff_home", "shot_attempt_diff_home", "home_sog", "away_sog",
    "manpower_diff_home", "home_power_play", "away_power_play", "even_strength",
    "home_active_penalty_seconds", "away_active_penalty_seconds",
    "home_empty_net", "away_empty_net",
    "home_power_play_opportunities", "away_power_play_opportunities",
    "home_power_play_goals", "away_power_play_goals",
    "faceoff_win_diff_home", "hit_diff_home",
    "home_takeaways", "away_takeaways", "home_giveaways", "away_giveaways",
    "home_goalie_save_pct_live", "away_goalie_save_pct_live",
    "home_goalie_saves", "away_goalie_saves",
    "target_home_win",
]


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    # +1 avoids div-by-zero at the final horn; sqrt is the standard time transform
    df["score_diff_per_sqrt_time"] = df["score_diff_home"] / np.sqrt(
        df["seconds_remaining_regulation"].clip(lower=0) + 1.0
    )
    df["is_playoff"] = (df["game_type"] == 3).astype(int)
    return df


def load() -> pd.DataFrame:
    df = pd.read_csv(LIVE_PATH, usecols=USECOLS)
    df = df[df["target_home_win"].notna()].copy()

    wf = pd.read_csv(WALKFWD_PATH, usecols=["game_id", "p_home"])
    wf = wf.rename(columns={"p_home": "pregame_home_prob"})
    df = df.merge(wf, on="game_id", how="left")
    # games without walk-forward coverage fall back to a neutral prior
    df["pregame_home_prob"] = df["pregame_home_prob"].fillna(0.54)
    return add_derived(df)


def make_model(seed: int = 7) -> HistGradientBoostingClassifier:
    monotonic = [1 if f in ("score_diff_home", "score_diff_per_sqrt_time",
                            "pregame_home_prob", "sog_diff_home") else 0
                 for f in LIVE_FEATURES]
    return HistGradientBoostingClassifier(
        max_iter=500, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=200, l2_regularization=2.0,
        monotonic_cst=monotonic,
        early_stopping=True, validation_fraction=0.1, random_state=seed,
    )


def main() -> None:
    df = load()
    print(f"events: {len(df):,}  games: {df.game_id.nunique():,}")

    train = df[df["season"] < 20252026]
    test = df[df["season"] == 20252026]
    print(f"train events: {len(train):,} ({train.game_id.nunique():,} games)  "
          f"test events: {len(test):,} ({test.game_id.nunique():,} games)")

    Xtr = train[LIVE_FEATURES].to_numpy(dtype=float)
    ytr = train["target_home_win"].astype(int).to_numpy()
    Xte = test[LIVE_FEATURES].to_numpy(dtype=float)
    yte = test["target_home_win"].astype(int).to_numpy()

    model = make_model()
    model.fit(Xtr, ytr)

    # isotonic calibration fitted on train-side out-of-fold-ish predictions is
    # ideal; with 1.3M rows, calibrating on the raw train predictions is stable
    p_tr = model.predict_proba(Xtr)[:, 1]
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(p_tr, ytr)

    p_raw = model.predict_proba(Xte)[:, 1]
    p = iso.predict(p_raw)

    print("\n=== 2025-26 held-out season ===")
    print(f"log_loss {log_loss(yte, p):.4f}  auc {roc_auc_score(yte, p):.4f}  "
          f"brier {brier_score_loss(yte, p):.4f}  "
          f"acc {(np.round(p) == yte).mean():.4f}")

    print("\nBy game phase (game_progress bucket):")
    test = test.assign(p=p)
    buckets = pd.cut(test["game_progress"].clip(0, 1), [0, .2, .4, .6, .8, .95, 1.0])
    rows = []
    for b, g in test.groupby(buckets, observed=True):
        yb, pb = g["target_home_win"].astype(int), g["p"]
        rows.append({
            "phase": str(b), "n": len(g),
            "acc": ((pb >= 0.5).astype(int) == yb).mean(),
            "log_loss": log_loss(yb, pb, labels=[0, 1]),
            "auc": roc_auc_score(yb, pb),
        })
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # sanity: prob at puck drop should match pregame prior closely
    start = test[test["game_progress"] < 0.01]
    print(f"\npuck-drop: corr(live_p, pregame_prior) = "
          f"{np.corrcoef(start['p'], start['pregame_home_prob'])[0,1]:.3f}")

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": model, "iso": iso, "features": LIVE_FEATURES},
                MODEL_DIR / "live_model.joblib")
    print(f"\nsaved {MODEL_DIR / 'live_model.joblib'}")


if __name__ == "__main__":
    main()
