# WinThePuck — NHL Winner Prediction Model

Modeling layer on top of `../pipeline`. Research-grounded design:
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
- `train_live_model.py` / `live_server.py` — the separate **in-game** model.
  It updates a win probability shift by shift from play-by-play events, and is
  what the replay on both front ends is showing.
- `export_site_data.py` — writes the JSON the React front end reads into
  `../frontend/data/`.

`data/walkforward_predictions.csv` is the output of `train_evaluate.py`: the
probability the model gave all 5,592 test games before they were played. It is
committed because [`../model/evaluate_model.py`](../model/evaluate_model.py)
runs its experiments against it, and CI re-runs those on every push.

## Run

```bash
# refresh data (in ../pipeline)
python main.py --mode upcoming && python main.py --mode build-merged

# rebuild features, evaluate, predict
python3 build_model_dataset.py
python3 train_evaluate.py
python3 predict_upcoming.py
```

## On the 60% target

All-games accuracy lands around the public state of the art (~58–61%
depending on the season). The way past 60% is not a better model, it is
**selective prediction**: the model is measurably more accurate on the games
it is most confident about — 65.4% on the 2,356 games where it was at least
60% sure. `train_evaluate.py` prints the confidence-threshold table this comes
from.

That is a statement about where the model is reliable, not a strategy. The
odds shown anywhere in this project are the fair odds implied by the
probability with no bookmaker margin, the model does not beat a closing line,
and none of this is betting advice — see
[`../docs/MODEL_CARD.md`](../docs/MODEL_CARD.md) for the full set of caveats.
