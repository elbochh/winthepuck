# WinThePuck: the model itself

This is the modelling layer that sits on top of `../pipeline`. Before writing
any of it I went looking for what a realistic target actually is, because it is
easy to chase a number that nobody has ever hit:

- the published ceiling for single-game NHL prediction is around 62%
  (Weissbock et al. 2013)
- bookmaker closing lines land around 59% to 60%
- Elo on its own gets about 57%

So the goal here is a calibrated ensemble that clears 60% on the games it is
confident about, rather than a headline accuracy that will not survive testing.

## Files

- `build_model_dataset.py` merges FiveThirtyEight-style Elo (K=6, HFA=50, a
  margin-of-victory multiplier, 30% season reversion) and exponentially decayed
  form onto `merged_model_data.csv`, writing `data/model_dataset.csv`.
- `train_evaluate.py` runs the leakage-safe walk-forward evaluation. For each
  test season the models retrain monthly on strictly prior games. The ensemble
  is HistGradientBoosting plus L2 logistic regression plus CatBoost, averaged.
  It reports per-season accuracy, log loss, AUC and Brier score, along with the
  confidence-threshold table.
- `predict_upcoming.py` trains on all history, replays Elo state up to today,
  and predicts `upcoming_games.csv` into `data/upcoming_predictions.csv`.
- `train_live_model.py` and `live_server.py` are the separate **in-game** model.
  It updates a win probability shift by shift from play-by-play events, and it
  is what the replay on both front ends is showing.
- `export_site_data.py` writes the JSON that the React front end reads into
  `../frontend/data/`.

`data/walkforward_predictions.csv` is the output of `train_evaluate.py`: the
probability the model gave all 5,592 test games before they were played. It is
committed because [`../model/evaluate_model.py`](../model/evaluate_model.py) runs
its experiments against it, and CI re-runs those on every push.

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

All-games accuracy lands around the public state of the art, roughly 58% to 61%
depending on the season. The way past 60% is not a better model, it is
**selective prediction**: the model is measurably more accurate on the games it
is most confident about, at 65.4% on the 2,356 games where it was at least 60%
sure. `train_evaluate.py` prints the confidence-threshold table this comes from.

That is a statement about where the model is reliable, not a strategy. The odds
shown anywhere in this project are the fair odds implied by the probability with
no bookmaker margin, the model does not beat a closing line, and none of this is
betting advice. See [`../docs/MODEL_CARD.md`](../docs/MODEL_CARD.md) for the full
set of caveats.
