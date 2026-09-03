"""Walk-forward training + evaluation for NHL winner prediction.

Protocol (no leakage):
  - Games sorted chronologically. For each test season, retrain monthly:
    the model that predicts games in month M is trained only on games that
    ended before M began (all prior seasons + current season up to M).
  - Ensemble: HistGradientBoosting + L2 logistic regression + CatBoost,
    averaged, then evaluated on accuracy / log loss / AUC / Brier.
  - Confidence-threshold report: winrate when only picking games where the
    ensemble is more confident than a threshold.

Usage: python3 train_evaluate.py [--test-seasons 20222023 20232024 20242025 20252026]
"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

DATA_PATH = Path(__file__).resolve().parent / "data" / "model_dataset.csv"

DROP_COLS = {
    # identifiers, outcomes and text: never features
    "game_id", "season", "game_type", "game_date", "start_time_utc", "venue",
    "home_team", "away_team", "home_score", "away_score", "winner_team",
    "target_home_win", "home_last_starting_goalie_id", "home_last_starting_goalie_name",
    "away_last_starting_goalie_id", "away_last_starting_goalie_name",
}


def load_dataset() -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(DATA_PATH, parse_dates=["game_date"])
    df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)
    feature_cols = [
        c for c in df.columns
        if c not in DROP_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    return df, feature_cols


def make_models(seed: int = 7):
    hgb = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.03, max_leaf_nodes=15,
        min_samples_leaf=80, l2_regularization=5.0,
        early_stopping=True, validation_fraction=0.12, random_state=seed,
    )
    logit = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.05, max_iter=2000),
    )
    models = {"hgb": hgb, "logit": logit}
    try:
        from catboost import CatBoostClassifier
        models["catboost"] = CatBoostClassifier(
            iterations=600, learning_rate=0.03, depth=4,
            l2_leaf_reg=8.0, random_seed=seed, verbose=False,
            allow_writing_files=False,
        )
    except ImportError:
        pass
    return models


def walk_forward(df: pd.DataFrame, feature_cols: list[str], test_seasons: list[int],
                 burn_in_season: int = 20112012) -> pd.DataFrame:
    """Monthly-retrained expanding-window predictions for the test seasons."""
    df = df[df["season"] >= burn_in_season].reset_index(drop=True)
    y = df["target_home_win"].astype(int).to_numpy()
    X = df[feature_cols].to_numpy(dtype=float)

    preds = []
    for season in test_seasons:
        season_mask = df["season"] == season
        months = sorted(df.loc[season_mask, "game_date"].dt.to_period("M").unique())
        for month in months:
            test_idx = np.flatnonzero(season_mask & (df["game_date"].dt.to_period("M") == month))
            month_start = month.to_timestamp()
            train_idx = np.flatnonzero(df["game_date"] < month_start)
            if len(train_idx) < 2000:
                continue
            model_probs = {}
            for name, model in make_models().items():
                model.fit(X[train_idx], y[train_idx])
                model_probs[name] = model.predict_proba(X[test_idx])[:, 1]
            p_ens = np.mean(list(model_probs.values()), axis=0)
            chunk = pd.DataFrame({
                "game_id": df.loc[test_idx, "game_id"].values,
                "season": season,
                "game_date": df.loc[test_idx, "game_date"].values,
                "game_type": df.loc[test_idx, "game_type"].values,
                "y": y[test_idx],
                "p_home": p_ens,
                "elo_prob_home": df.loc[test_idx, "elo_prob_home"].values,
            })
            for name, p in model_probs.items():
                chunk[f"p_{name}"] = p
            preds.append(chunk)
        done = pd.concat(preds)
        n = (done["season"] == season).sum()
        print(f"  season {season}: predicted {n} games")
    return pd.concat(preds, ignore_index=True)


def report(preds: pd.DataFrame) -> None:
    def metrics(g: pd.DataFrame, col: str = "p_home") -> dict:
        pick_correct = (g[col] >= 0.5).astype(int) == g["y"]
        return {
            "n": len(g),
            "accuracy": pick_correct.mean(),
            "log_loss": log_loss(g["y"], g[col], labels=[0, 1]),
            "auc": roc_auc_score(g["y"], g[col]) if g["y"].nunique() > 1 else np.nan,
            "brier": brier_score_loss(g["y"], g[col]),
        }

    print("\n=== Per-season (ensemble, all games) ===")
    rows = [dict(season=s, **metrics(g)) for s, g in preds.groupby("season")]
    rows.append(dict(season="ALL", **metrics(preds)))
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    print("\n=== Model comparison (all test games) ===")
    model_cols = [c for c in preds.columns if c.startswith("p_")]
    rows = [dict(model=c, **metrics(preds, c)) for c in model_cols]
    rows.append(dict(model="elo_only", **metrics(preds, "elo_prob_home")))
    print(pd.DataFrame(rows).drop_duplicates("model").to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    print("\n=== Confidence-filtered picks (ensemble) ===")
    print(f"{'min_conf':>8} {'coverage':>9} {'n_picks':>8} {'winrate':>8}")
    for t in [0.50, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70]:
        conf = np.maximum(preds["p_home"], 1 - preds["p_home"])
        sel = preds[conf >= t]
        if len(sel) == 0:
            continue
        correct = ((sel["p_home"] >= 0.5).astype(int) == sel["y"]).mean()
        print(f"{t:>8.2f} {len(sel)/len(preds):>9.1%} {len(sel):>8} {correct:>8.1%}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-seasons", nargs="+", type=int,
                        default=[20222023, 20232024, 20242025, 20252026])
    args = parser.parse_args()

    df, feature_cols = load_dataset()
    print(f"dataset: {df.shape[0]} games, {len(feature_cols)} features")
    preds = walk_forward(df, feature_cols, args.test_seasons)
    out = Path(__file__).resolve().parent / "data" / "walkforward_predictions.csv"
    preds.to_csv(out, index=False)
    print(f"wrote {out}")
    report(preds)


if __name__ == "__main__":
    main()
