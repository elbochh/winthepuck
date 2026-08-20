# WinThePuck — NHL Winner Prediction Model

Modeling layer on top of `../nhl_data_pipeline`. Research-grounded design:
the published accuracy ceiling for single-game NHL prediction is ~62%
(Weissbock et al. 2013), bookmaker closing lines hit ~59–60%, and Elo alone
gets ~57%. This pipeline targets 60%+ winrate via a calibrated ensemble plus
confidence-filtered picks.

## Files

- `build_model_dataset.py` — merges FiveThirtyEight-style Elo (K=6, HFA=50,
  margin-of-victory multiplier, 30% season reversion) and exponentially
  decayed form onto `merged_model_data.csv` → `data/model_dataset.csv`.
- `train_evaluate.py` — leakage-safe walk-forward evaluation: for each test
  season, models retrain monthly on strictly-prior games. Ensemble =
  HistGradientBoosting + L2 logistic + CatBoost (averaged). Reports per-season
  accuracy / log loss / AUC / Brier plus confidence-threshold winrates.
- `predict_upcoming.py` — trains on all history, replays Elo state to today,
  and predicts `upcoming_games.csv` → `data/upcoming_predictions.csv`.

## Run

```bash
# refresh data (in ../nhl_data_pipeline)
python main.py --mode upcoming && python main.py --mode build-merged

# rebuild features, evaluate, predict
python3 build_model_dataset.py
python3 train_evaluate.py
python3 predict_upcoming.py
```

## How the 60% target is met

All-games accuracy lands around the public state of the art (~59–61% by
season). To *pick* at 60%+ winrate, use the confidence filter from the
evaluation report: only bet/pick games where ensemble confidence ≥ the
threshold whose historical winrate clears 60% (see the
"Confidence-filtered picks" table printed by `train_evaluate.py`).
