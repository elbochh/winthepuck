"""Train the prediction model once and save everything the cloud needs.

This script is the heavy one. We run it on our own laptops (it needs the
18 GB data pipeline output), and it writes three small files into `serving/`:

  pregame_model.joblib   the trained ensemble (gradient boosting + logistic
                         regression + CatBoost), about 3 MB
  team_state.json        every team's Elo rating, recent-form numbers and last
                         known season stats on the day the season ended
  model_report.json      the honest accuracy numbers from the Phase 2
                         walk-forward test, so the website can show them

Those three files are small enough to put in GitHub, which means the daily
refresh job in the cloud never has to touch the big data pipeline again.

    python3 build_serving_bundle.py
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import elo

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
NHL_MODEL = HERE.parent.parent / "nhl_model"
DATASET = NHL_MODEL / "data" / "model_dataset.csv"
WALKFORWARD = NHL_MODEL / "data" / "walkforward_predictions.csv"
OUT = HERE / "serving"

# Columns that are names, dates or the answer itself - never inputs.
DROP_COLS = {
    "game_id", "season", "game_type", "game_date", "start_time_utc", "venue",
    "home_team", "away_team", "home_score", "away_score", "winner_team",
    "target_home_win", "home_last_starting_goalie_id",
    "home_last_starting_goalie_name", "away_last_starting_goalie_id",
    "away_last_starting_goalie_name",
}


def make_models(seed: int = 7) -> dict:
    """The same three models the Phase 2 report tested."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    models = {
        "hgb": HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.03, max_leaf_nodes=15,
            min_samples_leaf=80, l2_regularization=5.0,
            early_stopping=True, validation_fraction=0.12, random_state=seed,
        ),
        "logit": make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(C=0.05, max_iter=2000),
        ),
    }
    try:
        from catboost import CatBoostClassifier
        models["catboost"] = CatBoostClassifier(
            iterations=600, learning_rate=0.03, depth=4, l2_leaf_reg=8.0,
            random_seed=seed, verbose=False, allow_writing_files=False,
        )
    except ImportError:
        print("CatBoost not installed - training with two models instead of three")
    return models


def load_dataset() -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(DATASET, parse_dates=["game_date"])
    df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)
    feature_cols = [
        c for c in df.columns
        if c not in DROP_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    return df, feature_cols


def train(df: pd.DataFrame, feature_cols: list[str]) -> dict:
    """Fit every model on every completed game we have."""
    X = df[feature_cols].to_numpy(dtype=float)
    y = df["target_home_win"].astype(int).to_numpy()
    print(f"training on {len(df):,} games and {len(feature_cols)} features")

    trained = {}
    for name, model in make_models().items():
        started = datetime.now()
        model.fit(X, y)
        seconds = (datetime.now() - started).total_seconds()
        print(f"  {name:<9} trained in {seconds:5.1f}s")
        trained[name] = model
    return trained


def team_states(df: pd.DataFrame) -> dict[str, elo.TeamState]:
    """Replay every game in order so we know where each team stands today."""
    states: dict[str, elo.TeamState] = {}

    for game in df.itertuples(index=False):
        home, away, season = game.home_team, game.away_team, int(game.season)
        for team in (home, away):
            if team not in states:
                states[team] = elo.TeamState(season=season)
            else:
                elo.start_new_season(states[team], season)
        elo.apply_result(states[home], states[away],
                         int(game.home_score), int(game.away_score),
                         int(game.game_type))
    return states


# The refresh job works these out itself from the real scores, so there is
# no point saving a stale copy of them.
RECOMPUTED = {
    "elo_pre", "decay_goal_diff", "decay_win_rate",
    "rest_days", "back_to_back",
    "games_last_3_days", "games_last_7_days", "games_last_14_days",
    "last_5_win_pct", "last_10_win_pct",
    "last_5_goals_for_avg", "last_5_goals_against_avg", "goal_diff_last_10",
    "season_points_pct_before_game",
    "home_win_pct_before_game", "road_win_pct_before_game",
    "home_goal_diff_avg_before_game", "road_goal_diff_avg_before_game",
    # playoff-only columns, meaningless for a regular season game
    "series_wins_before", "elimination_game",
}


def latest_features(df: pd.DataFrame, feature_cols: list[str]) -> dict[str, dict]:
    """
    For each team, remember the box-score numbers from its most recent game.

    Things like "shots in the last 10 games" or "save percentage of the last
    starting goalie" come from the full data pipeline, which is far too big to
    run in the cloud, so the refresh job reuses the last value it knows.
    Everything the free NHL API can give us (ratings, form, records, rest) is
    recalculated for real every day instead.
    """
    generic = sorted(({
        c[len("home_"):] for c in feature_cols if c.startswith("home_")
    } & {
        c[len("away_"):] for c in feature_cols if c.startswith("away_")
    }) - RECOMPUTED)

    out: dict[str, dict] = {}
    for team in sorted(set(df["home_team"]) | set(df["away_team"])):
        played = df[(df["home_team"] == team) | (df["away_team"] == team)]
        # a regular season game is a fairer starting point than a playoff game
        regular = played[played["game_type"] == 2]
        played = regular if not regular.empty else played
        if played.empty:
            continue
        row = played.iloc[-1]
        side = "home" if row["home_team"] == team else "away"
        values = {}
        for name in generic:
            value = row.get(f"{side}_{name}")
            if pd.notna(value):
                values[name] = float(value)
        out[team] = values
    return out


def model_report() -> dict:
    """Real accuracy numbers from the Phase 2 walk-forward test."""
    if not WALKFORWARD.exists():
        return {}
    wf = pd.read_csv(WALKFORWARD, parse_dates=["game_date"])
    confidence = np.maximum(wf["p_home"], 1 - wf["p_home"])
    correct = (wf["p_home"] >= 0.5).astype(int) == wf["y"]

    per_model = []
    names = {"p_home": "WinThePuck Ensemble", "p_logit": "Logistic Regression",
             "p_hgb": "Gradient Boosting", "p_catboost": "CatBoost",
             "elo_prob_home": "Elo Baseline"}
    for column, label in names.items():
        if column not in wf.columns:
            continue
        hits = (wf[column] >= 0.5).astype(int) == wf["y"]
        log_loss = -(wf["y"] * np.log(wf[column].clip(1e-9))
                     + (1 - wf["y"]) * np.log((1 - wf[column]).clip(1e-9))).mean()
        best = streak = 0
        for value in hits.to_numpy():
            streak = streak + 1 if value else 0
            best = max(best, streak)
        per_model.append({
            "model": label,
            "accuracy": round(100 * hits.mean(), 1),
            "logLoss": round(float(log_loss), 4),
            "correctPicks": int(hits.sum()),
            "games": int(len(wf)),
            "bestStreak": int(best),
        })
    per_model.sort(key=lambda r: -r["accuracy"])
    for index, row in enumerate(per_model):
        row["rank"] = index + 1

    buckets = []
    for low, high in [(0.50, 0.55), (0.55, 0.60), (0.60, 0.65),
                      (0.65, 0.70), (0.70, 1.01)]:
        picked = wf[(confidence >= low) & (confidence < high)]
        if len(picked):
            hits = (picked["p_home"] >= 0.5).astype(int) == picked["y"]
            buckets.append({
                "range": f"{int(low * 100)}-{int(min(high, 1) * 100)}%",
                "games": int(len(picked)),
                "accuracy": round(100 * hits.mean(), 1),
            })

    seasons = []
    for season, group in wf.groupby("season"):
        hits = (group["p_home"] >= 0.5).astype(int) == group["y"]
        seasons.append({
            "season": f"{str(season)[:4]}-{str(season)[6:]}",
            "games": int(len(group)),
            "accuracy": round(100 * hits.mean(), 1),
        })

    confident = wf[confidence >= 0.60]
    confident_hits = (confident["p_home"] >= 0.5).astype(int) == confident["y"]
    return {
        "testedGames": int(len(wf)),
        "testedSeasons": len(seasons),
        "overallAccuracy": round(100 * correct.mean(), 1),
        "confidentAccuracy": round(100 * confident_hits.mean(), 1),
        "confidentGames": int(len(confident)),
        "perModel": per_model,
        "perSeason": seasons,
        "confidenceBuckets": buckets,
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df, feature_cols = load_dataset()

    trained = train(df, feature_cols)
    joblib.dump({"models": trained, "feature_cols": feature_cols},
                OUT / "pregame_model.joblib", compress=3)
    size_mb = (OUT / "pregame_model.joblib").stat().st_size / 1e6
    print(f"wrote serving/pregame_model.joblib ({size_mb:.1f} MB)")

    states = team_states(df)
    features = latest_features(df, feature_cols)
    last_game = df.iloc[-1]
    payload = {
        "asOfDate": str(last_game["game_date"])[:10],
        "asOfGameId": int(last_game["game_id"]),
        "season": int(last_game["season"]),
        "seasonGameIndex": int(df["season_game_index"].max()),
        "teams": {
            team: {**state.to_dict(), "features": features.get(team, {})}
            for team, state in sorted(states.items())
        },
    }
    (OUT / "team_state.json").write_text(json.dumps(payload, indent=1))
    print(f"wrote serving/team_state.json ({len(states)} teams, "
          f"as of {payload['asOfDate']})")

    report = model_report()
    if report:
        (OUT / "model_report.json").write_text(json.dumps(report, indent=1))
        print(f"wrote serving/model_report.json "
              f"(accuracy {report['overallAccuracy']}% over "
              f"{report['testedGames']:,} tested games)")


if __name__ == "__main__":
    main()
