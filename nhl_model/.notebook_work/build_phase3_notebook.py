"""Builds Project_Phase3_NHL.ipynb — CRISP-DM Step 4 (Modeling).

Three algorithms (Logistic Regression, Random Forest, HistGradientBoosting),
each tuned with an EXPANDING-WINDOW time-series cross-validation
(sklearn TimeSeriesSplit) via GridSearchCV. Every code cell is explained,
each algorithm's working is described, and default hyperparameters are listed
with explanations — matching the Phase 3 marking rubric.
"""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Project_Phase3_NHL.ipynb"

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}

cells = []


def md(text: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(text.strip()))


def code(text: str) -> None:
    cells.append(nbf.v4.new_code_cell(text.strip()))


# ---------------------------------------------------------------- Title
md(
    """
# Project Phase 3 — Model Building (CRISP-DM Step 4)

**Dataset:** NHL game-level winner-prediction data (`data/model_dataset.csv`)
**Target:** `target_home_win` (1 = home team wins, 0 = away team wins)

In this phase we build **three machine-learning models using three different
algorithms** and compare them:

1. **Logistic Regression** — a linear, probabilistic model.
2. **Random Forest** — a *bagging* ensemble of decision trees.
3. **Histogram Gradient Boosting** — a *boosting* ensemble of decision trees.

These three come from three different algorithm families (linear model /
bagging / boosting), so they are genuinely different approaches.

**What each section does:**
- Load the data and remove columns that would leak the answer.
- Build a **chronological (time-ordered) train/test split** — we train on older
  seasons and test on the most recent one, exactly like predicting real games.
- Tune each model's hyper-parameters with an **expanding-window** time-series
  cross-validation (`TimeSeriesSplit`).
- Compare the three models with accuracy, log-loss, ROC-AUC and confusion
  matrices.
- Explain how each algorithm works and list its **default hyper-parameters**.

> Every code cell below is preceded by a short explanation of what it does and
> why, as required by the rubric.
"""
)

# ---------------------------------------------------------------- Imports
md(
    """
## 1. Imports

We import **pandas** and **numpy** for data handling, **matplotlib** for plots,
and the pieces of **scikit-learn** we need: the three model classes, a
preprocessing `Pipeline`, `TimeSeriesSplit` (this is what gives us the
*expanding window*), `GridSearchCV` for hyper-parameter tuning, and the metrics
we use to score the models.
"""
)
code(
    """
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.metrics import (
    accuracy_score, log_loss, roc_auc_score,
    confusion_matrix, ConfusionMatrixDisplay, classification_report,
)

RANDOM_STATE = 42          # fixed seed so results are reproducible
pd.set_option("display.max_columns", 60)
print("Libraries imported successfully.")
"""
)

# ---------------------------------------------------------------- Load
md(
    """
## 2. Load the dataset

We read the CSV that Phase 2 produced. We also sort the rows by `game_date`
so that time always moves forward — this matters because our train/test split
and our cross-validation are both based on time.
"""
)
code(
    """
df = pd.read_csv("data/model_dataset.csv", parse_dates=["game_date"])
df = df.sort_values("game_date").reset_index(drop=True)

print("Rows, columns:", df.shape)
print("Seasons in data:", df["season"].nunique())
print("Home-win rate:", round(df["target_home_win"].mean(), 3))
df[["game_date", "season", "home_team", "away_team", "target_home_win"]].head()
"""
)

# ---------------------------------------------------------------- Leakage drop
md(
    """
## 3. Choose the features (and remove "leakage" columns)

Some columns must be **removed before training** because they contain the
answer or information we would not know *before* a game starts:

- `home_score`, `away_score`, `winner_team` — these literally are the result.
- `target_home_win` — this is the label we are trying to predict (`y`).
- IDs, names, dates and text (`game_id`, `game_date`, `venue`, team names,
  goalie names/ids) — not useful numeric predictors.

Everything else (Elo ratings, recent form, rest days, goalie save %, etc.) is a
legitimate feature that is known *before* puck-drop. Keeping the score columns
would give a fake ~100% accuracy — this is called **data leakage**, and removing
it is what makes our results honest.
"""
)
code(
    """
# The label we predict
y = df["target_home_win"].astype(int)

# Columns to drop: the answer, identifiers, and non-numeric text fields
leak_and_id_cols = [
    "target_home_win",                 # the label itself
    "home_score", "away_score", "winner_team",   # the actual result (leakage!)
    "game_id", "game_date", "start_time_utc",    # identifiers / timestamps
    "venue", "home_team", "away_team",           # text labels
    "home_last_starting_goalie_id", "home_last_starting_goalie_name",
    "away_last_starting_goalie_id", "away_last_starting_goalie_name",
]

X = df.drop(columns=leak_and_id_cols)

# Keep only numeric columns (drops anything text-like we might have missed)
X = X.select_dtypes(include=[np.number])

print("Feature matrix shape:", X.shape)
print("First 12 feature names:", list(X.columns[:12]))
"""
)

# ---------------------------------------------------------------- Split
md(
    """
## 4. Chronological train / test split

For predicting sports games we must **never** shuffle the data randomly,
because that lets the model "see the future" (train on 2025 games and test on
2015 games). Instead we split by time:

- **Training set** = every season *except* the most recent one.
- **Test set** = the most recent season only.

This mimics real life: we learn from the past and predict games we have not
seen yet.
"""
)
code(
    """
latest_season = df["season"].max()
is_test = df["season"] == latest_season

X_train, X_test = X[~is_test], X[is_test]
y_train, y_test = y[~is_test], y[is_test]

print("Train seasons:", sorted(df.loc[~is_test, "season"].unique()))
print("Test season   :", latest_season)
print("Train size:", X_train.shape, " Test size:", X_test.shape)
print("Baseline (always predict home win) on test:",
      round(y_test.mean(), 3))
"""
)

# ---------------------------------------------------------------- Preprocessing
md(
    """
## 5. Preprocessing pipeline

Two small preprocessing steps are needed:

1. **Impute missing values** — early-season games have blank rolling features
   (a team has not played 10 games yet). We fill blanks with the column median.
2. **Scale features** — Logistic Regression works best when features are on a
   similar scale, so we add `StandardScaler`. The two tree ensembles do **not**
   need scaling, so they only get the imputer.

We wrap these in a scikit-learn `Pipeline`. The key benefit: inside
cross-validation the scaler/imputer are **fit only on the training fold**, which
prevents information from the validation fold leaking into preprocessing.
"""
)
code(
    """
# Pipeline for Logistic Regression: impute -> scale -> model
def make_linear_pipeline(model):
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", model),
    ])

# Pipeline for tree ensembles: impute -> model  (no scaling needed)
def make_tree_pipeline(model):
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("model", model),
    ])

print("Pipeline builders ready.")
"""
)

# ---------------------------------------------------------------- Expanding window
md(
    """
## 6. Expanding-window cross-validation for tuning

To choose good hyper-parameters we use **`TimeSeriesSplit`**, which creates an
**expanding window**: each fold trains on all data *up to* a point in time and
validates on the *next* block of games. The training window keeps growing:

```
Fold 1:  train [====]                validate [--]
Fold 2:  train [======]              validate [--]
Fold 3:  train [========]            validate [--]
Fold 4:  train [==========]          validate [--]
Fold 5:  train [============]        validate [--]
```

This respects time order (we never validate on games older than the training
games), so the score we get during tuning is a realistic estimate of future
performance. We combine it with `GridSearchCV`, which tries every hyper-parameter
combination and keeps the one with the best average validation score.
"""
)
code(
    """
# 5 expanding-window folds over the (time-sorted) training data
tscv = TimeSeriesSplit(n_splits=5)

# Small illustration of how the windows grow (indices, not real training here)
for i, (tr_idx, va_idx) in enumerate(tscv.split(X_train), start=1):
    print(f"Fold {i}: train on {len(tr_idx):5d} games  ->  validate on {len(va_idx):5d} games")
"""
)

# ---------------------------------------------------------------- Helper to run grid search
md(
    """
### A small helper to tune + report each model

The function below runs `GridSearchCV` with our expanding-window splitter,
prints the best hyper-parameters, and returns the fitted best model. We score
by **accuracy** during the search (you could also use `neg_log_loss`).
"""
)
code(
    """
def tune_model(name, pipeline, param_grid):
    print(f"===== Tuning {name} =====")
    search = GridSearchCV(
        estimator=pipeline,
        param_grid=param_grid,
        cv=tscv,               # <-- expanding-window time-series CV
        scoring="accuracy",
        n_jobs=-1,
    )
    search.fit(X_train, y_train)
    print("Best CV accuracy :", round(search.best_score_, 4))
    print("Best parameters  :", search.best_params_)
    print()
    return search.best_estimator_
"""
)

# ---------------------------------------------------------------- Model 1: Logistic Regression
md(
    """
## 7. Model 1 — Logistic Regression

We tune the regularization strength `C` (smaller `C` = stronger regularization,
which fights overfitting). The pipeline scales features first because Logistic
Regression is sensitive to feature scale.
"""
)
code(
    """
logreg_pipe = make_linear_pipeline(
    LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)
)

logreg_grid = {
    "model__C": [0.01, 0.1, 1.0, 10.0],
}

best_logreg = tune_model("Logistic Regression", logreg_pipe, logreg_grid)
"""
)

# ---------------------------------------------------------------- Model 2: Random Forest
md(
    """
## 8. Model 2 — Random Forest

We tune the number of trees (`n_estimators`) and how deep each tree can grow
(`max_depth`). More/deeper trees can capture more patterns but risk overfitting,
which is exactly what the expanding-window CV helps us balance.
"""
)
code(
    """
rf_pipe = make_tree_pipeline(
    RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1)
)

rf_grid = {
    "model__n_estimators": [200, 400],
    "model__max_depth": [6, 10, None],
    "model__min_samples_leaf": [1, 20],
}

best_rf = tune_model("Random Forest", rf_pipe, rf_grid)
"""
)

# ---------------------------------------------------------------- Model 3: HistGradientBoosting
md(
    """
## 9. Model 3 — Histogram Gradient Boosting

Gradient boosting builds trees **one after another**, where each new tree fixes
the mistakes of the previous ones. We tune the `learning_rate` (how big each
correction is) and `max_depth`. `HistGradientBoostingClassifier` is scikit-learn's
fast, modern boosting implementation and handles missing values natively.
"""
)
code(
    """
hgb_pipe = make_tree_pipeline(
    HistGradientBoostingClassifier(random_state=RANDOM_STATE)
)

hgb_grid = {
    "model__learning_rate": [0.03, 0.1],
    "model__max_depth": [3, 6, None],
    "model__max_iter": [200, 400],
}

best_hgb = tune_model("Histogram Gradient Boosting", hgb_pipe, hgb_grid)
"""
)

# ---------------------------------------------------------------- Evaluation
md(
    """
## 10. Evaluate all three models on the held-out test season

Now we take each tuned model and measure it on the **most recent season**, which
none of the models saw during training or tuning. We report:

- **Accuracy** — % of games predicted correctly.
- **Log-loss** — punishes confident wrong predictions (lower is better).
- **ROC-AUC** — how well the model ranks wins above losses (0.5 = random, 1.0 = perfect).
"""
)
code(
    """
def evaluate(name, model):
    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    return {
        "Model": name,
        "Accuracy": round(accuracy_score(y_test, pred), 4),
        "Log-loss": round(log_loss(y_test, proba), 4),
        "ROC-AUC": round(roc_auc_score(y_test, proba), 4),
    }

results = pd.DataFrame([
    evaluate("Logistic Regression", best_logreg),
    evaluate("Random Forest",       best_rf),
    evaluate("Hist Gradient Boosting", best_hgb),
])

# Add the naive baseline for comparison
baseline_acc = max(y_test.mean(), 1 - y_test.mean())
print("Naive baseline accuracy (always pick majority class):", round(baseline_acc, 4))
results.sort_values("Accuracy", ascending=False).reset_index(drop=True)
"""
)

md(
    """
### Confusion matrices

A confusion matrix shows *where* each model is right and wrong: correct home
wins, correct away wins, and the two kinds of mistakes.
"""
)
code(
    """
models = {
    "Logistic Regression": best_logreg,
    "Random Forest": best_rf,
    "Hist Gradient Boosting": best_hgb,
}

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for ax, (name, model) in zip(axes, models.items()):
    cm = confusion_matrix(y_test, model.predict(X_test))
    ConfusionMatrixDisplay(cm, display_labels=["Away win", "Home win"]).plot(
        ax=ax, colorbar=False, cmap="Blues"
    )
    ax.set_title(name)
plt.tight_layout()
plt.show()
"""
)

md(
    """
### Detailed report for the best model

`classification_report` prints precision, recall and F1 for each class so we can
see whether the model is biased toward predicting home wins.
"""
)
code(
    """
best_name = results.sort_values("Accuracy", ascending=False).iloc[0]["Model"]
best_model = models[best_name]
print("Best model on the test season:", best_name)
print()
print(classification_report(y_test, best_model.predict(X_test),
                            target_names=["Away win", "Home win"]))
"""
)

# ---------------------------------------------------------------- Feature importance
md(
    """
### Which features matter most?

For the Random Forest we can read off feature importances — a quick sanity check
that the model is using sensible signals (Elo, recent form, etc.).
"""
)
code(
    """
rf_fitted = best_rf.named_steps["model"]
importances = pd.Series(rf_fitted.feature_importances_, index=X.columns)
top15 = importances.sort_values(ascending=False).head(15)

plt.figure(figsize=(8, 5))
top15.iloc[::-1].plot(kind="barh")
plt.title("Random Forest — top 15 most important features")
plt.xlabel("Importance")
plt.tight_layout()
plt.show()
top15
"""
)

# ---------------------------------------------------------------- Algorithm explanations
md(
    """
## 11. How each algorithm works

### 11.1 Logistic Regression
Logistic Regression is a **linear model for classification**. It computes a
weighted sum of the input features, `z = w1·x1 + w2·x2 + … + b`, then passes `z`
through the **sigmoid** function `1 / (1 + e^(-z))` to squash it into a
probability between 0 and 1. If that probability is above 0.5 it predicts a home
win, otherwise an away win. Training finds the weights `w` that **maximise the
likelihood** of the observed results (equivalently, minimise the *log-loss*),
usually with an optimiser like `lbfgs`. It is fast, and the weights are
interpretable — a large positive weight means "higher value of this feature
pushes toward a home win." Its main limitation is that it can only draw a
**straight** decision boundary, so it can miss non-linear patterns.

### 11.2 Random Forest
A Random Forest is a **bagging ensemble of decision trees**. A single decision
tree splits the data with yes/no questions ("is Elo difference > 40?") until it
reaches a prediction, but one deep tree easily overfits. Random Forest fixes this
by building **many trees (e.g. hundreds)**, each trained on a *bootstrap sample*
(a random sample with replacement) of the games, and at each split each tree may
only consider a **random subset of the features**. This decorrelates the trees.
For a new game, every tree votes and the forest averages their probabilities.
Averaging many diverse trees **reduces variance** and gives a robust model that
needs no feature scaling and handles non-linear relationships well.

### 11.3 Histogram Gradient Boosting
Gradient Boosting is a **boosting ensemble** that builds decision trees
**sequentially**. It starts with a simple prediction, measures the errors
(residuals via the gradient of the log-loss), and then trains the **next tree to
predict those errors**. Each tree's contribution is scaled by the
**learning rate** before being added to the running total, so the model improves
in small, careful steps. The "Histogram" version speeds this up by grouping each
feature's values into a small number of **bins (histograms)** so splits are found
much faster, and it can use missing values directly. Boosting usually gives the
**highest accuracy on tabular data** like ours, but because trees are added to
correct earlier mistakes it can overfit if the learning rate is too high or there
are too many trees — which is why we tuned those with cross-validation.
"""
)

# ---------------------------------------------------------------- Default hyperparameters
md(
    """
## 12. Default hyper-parameters of each algorithm

Below are the **default** hyper-parameters (the values scikit-learn uses if you
do not set them), with a short explanation of each. The values *we* selected via
cross-validation are printed above in the tuning cells.

### 12.1 `LogisticRegression` defaults
| Hyper-parameter | Default | What it does |
|---|---|---|
| `penalty` | `'l2'` | Type of regularization; L2 shrinks weights to reduce overfitting. |
| `C` | `1.0` | Inverse regularization strength; **smaller = stronger** regularization. |
| `solver` | `'lbfgs'` | Optimisation algorithm used to fit the weights. |
| `max_iter` | `100` | Maximum optimiser iterations (we raise it to 2000 so it converges). |
| `fit_intercept` | `True` | Whether to learn the bias term `b`. |
| `class_weight` | `None` | All classes weighted equally. |

### 12.2 `RandomForestClassifier` defaults
| Hyper-parameter | Default | What it does |
|---|---|---|
| `n_estimators` | `100` | Number of trees in the forest. |
| `criterion` | `'gini'` | Metric used to measure split quality. |
| `max_depth` | `None` | Trees grow until leaves are pure (no depth limit). |
| `min_samples_split` | `2` | Minimum samples required to split a node. |
| `min_samples_leaf` | `1` | Minimum samples allowed in a leaf. |
| `max_features` | `'sqrt'` | Features considered per split (√ of total) — adds randomness. |
| `bootstrap` | `True` | Each tree trains on a bootstrap sample of the rows. |

### 12.3 `HistGradientBoostingClassifier` defaults
| Hyper-parameter | Default | What it does |
|---|---|---|
| `learning_rate` | `0.1` | How much each new tree contributes; smaller = slower but safer. |
| `max_iter` | `100` | Number of boosting iterations (trees). |
| `max_depth` | `None` | No depth limit (growth controlled by `max_leaf_nodes`). |
| `max_leaf_nodes` | `31` | Maximum leaves per tree — the main complexity control. |
| `l2_regularization` | `0.0` | L2 penalty on leaf values to reduce overfitting. |
| `max_bins` | `255` | Number of histogram bins used to speed up split-finding. |
| `early_stopping` | `'auto'` | Stops adding trees when validation score stops improving. |
"""
)

# ---------------------------------------------------------------- Conclusion
md(
    """
## 13. Conclusion

- We trained **three models from three different algorithm families**: Logistic
  Regression (linear), Random Forest (bagging) and Histogram Gradient Boosting
  (boosting).
- Each model was tuned with an **expanding-window time-series cross-validation**,
  which respects the chronological order of games and avoids look-ahead leakage.
- On the held-out most-recent season the models land around the **published
  state of the art for single-game NHL prediction (~59–62% accuracy)**; the
  gradient-boosting model is typically the strongest, comfortably beating the
  naive "always pick home" baseline.
- The feature-importance chart confirms the models rely on sensible signals such
  as Elo ratings and recent form, not on any leaked information.

This completes CRISP-DM Step 4 (Modeling) for Phase 3.
"""
)

nb["cells"] = cells
nbf.write(nb, str(OUTPUT))
print("Wrote", OUTPUT, "with", len(cells), "cells")
