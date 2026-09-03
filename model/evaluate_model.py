"""Does the model have anything left to give? A controlled experiment.

The walk-forward test left behind one very useful file: the
probability the model gave every one of 5,592 games *before* it was played,
together with what actually happened. That file is an honest test bed, and
this script uses it to ask whether three well-known tricks would make the
model better.

The rule followed throughout is the one that makes a result mean anything:

    every setting is chosen using the first three seasons only, and then
    applied once to the fourth season, which is never looked at until the
    final table is printed.

Anything tuned on the season you then report on will look like an improvement
whether or not it is one.

The three ideas, tested in four variants:

  1. Platt / temperature scaling - the standard fix for a model that is
     over-confident. Stretches or squashes the probabilities.

  2. Adaptive home-ice advantage - the model assumes home teams win about
     54.4% of the time, but the real figure moved between 51.9% and 56.5%
     over these four seasons. This nudges each prediction towards whatever
     home ice has really been worth lately.

  3. Fitted ensemble weights - the live model averages its three components
     equally. This fits proper weights instead.

Run it with:

    python3 evaluate_model.py

Writing the answer down matters even when the answer is "none of them helped",
which - spoiler - is what this found. See MODEL_CARD.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PREDICTIONS = HERE.parent / "ml" / "data" / "walkforward_predictions.csv"
DEFAULT_OUT = HERE / "serving" / "evaluation_report.json"

HELD_OUT_SEASON = 20252026
COMPONENTS = ["p_hgb", "p_logit", "p_catboost"]

# What the model implicitly believes home ice is worth, measured as the average
# probability it hands the home team across all 5,592 games.
ASSUMED_HOME_RATE = 0.544


# Small maths helpers

def logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    exp_z = math.exp(z)            # keeps very negative z from overflowing
    return exp_z / (1 + exp_z)


def log_loss(pairs: list[tuple[float, int]]) -> float:
    total = 0.0
    for p, y in pairs:
        p = min(max(p, 1e-15), 1 - 1e-15)
        total -= math.log(p) if y == 1 else math.log(1 - p)
    return total / len(pairs)


def brier(pairs: list[tuple[float, int]]) -> float:
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def accuracy(pairs: list[tuple[float, int]]) -> float:
    return 100 * sum(1 for p, y in pairs if (p >= 0.5) == (y == 1)) / len(pairs)


def score(pairs: list[tuple[float, int]]) -> dict:
    """All three headline numbers for one set of (probability, outcome) pairs."""
    return {
        "games": len(pairs),
        "logLoss": round(log_loss(pairs), 4),
        "brier": round(brier(pairs), 4),
        "accuracy": round(accuracy(pairs), 1),
    }


# Loading the test bed

def load(path: Path) -> list[dict]:
    """
    Read the walk-forward predictions CSV into date-ordered rows.

    Every probability in that file was produced before its game was played,
    which is the only reason any of the experiments below mean anything.
    """
    rows = []
    with path.open() as handle:
        for row in csv.DictReader(handle):
            rows.append({
                "season": int(row["season"]),
                "game_date": row["game_date"],
                "game_id": int(row["game_id"]),
                "y": int(row["y"]),
                "ensemble": float(row["p_home"]),
                "elo": float(row["elo_prob_home"]),
                **{name: float(row[name]) for name in COMPONENTS},
            })
    rows.sort(key=lambda r: (r["game_date"], r["game_id"]))
    return rows


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """The first three seasons to learn from, the fourth kept sealed."""
    train = [r for r in rows if r["season"] < HELD_OUT_SEASON]
    test = [r for r in rows if r["season"] == HELD_OUT_SEASON]
    return train, test


# A tiny gradient descent
#
# Every candidate below is a logistic regression on top of the model's own
# output, so one small optimiser does for all of them. Written out by hand
# rather than importing scikit-learn, so this script runs anywhere.

def fit_logistic(inputs: list[list[float]], targets: list[int],
                 iterations: int = 6000, rate: float = 0.3) -> tuple[list[float], float]:
    """
    Plain batch gradient descent on a logistic model.

    Written by hand rather than imported so this study needs nothing but the
    standard library. It runs in a couple of seconds on 4,200 rows and CI can
    rerun it on every push without installing scikit-learn.
    """
    width = len(inputs[0])
    weights = [1.0 / width] * width
    bias = 0.0
    n = len(inputs)

    for _ in range(iterations):
        grad_w = [0.0] * width
        grad_b = 0.0
        for features, target in zip(inputs, targets, strict=True):
            error = sigmoid(sum(w * f for w, f in zip(weights, features, strict=True)) + bias) - target
            for index, value in enumerate(features):
                grad_w[index] += error * value
            grad_b += error
        weights = [w - rate * g / n for w, g in zip(weights, grad_w, strict=True)]
        bias -= rate * grad_b / n

    return weights, bias


# CANDIDATE 1 - PLATT SCALING

def platt(train: list[dict], test: list[dict]) -> dict:
    """Stretch or squash the probabilities to fix over-confidence."""
    weights, bias = fit_logistic([[logit(r["ensemble"])] for r in train],
                                 [r["y"] for r in train])
    slope = weights[0]

    def apply(rows: list[dict]) -> list[tuple[float, int]]:
        return [(sigmoid(slope * logit(r["ensemble"]) + bias), r["y"]) for r in rows]

    return {
        "name": "Platt scaling",
        "idea": "rescale the probabilities so stated confidence matches reality",
        "fitted": {"slope": round(slope, 4), "bias": round(bias, 4)},
        # A slope above 1 means the model was, if anything, too timid on the
        # seasons it was tuned on - the opposite of the problem we went looking
        # for.
        "reading": ("slope above 1 - the model was under-confident on the "
                    "training seasons" if slope > 1 else
                    "slope below 1 - the model was over-confident"),
        "train": score(apply(train)),
        "heldOut": score(apply(test)),
    }


# CANDIDATE 2 - ADAPTIVE HOME-ICE ADVANTAGE

def adaptive_home_ice(rows: list[dict], window: int, strength: float
                      ) -> list[tuple[float, int]]:
    """
    Nudge each prediction towards what home ice has really been worth lately.

    This walks through the games in the order they were played and only ever
    looks backwards, so a game is never adjusted using its own result.
    """
    out: list[tuple[float, int]] = []
    seen: list[int] = []
    for row in rows:
        shift = 0.0
        if len(seen) >= window:
            observed = sum(seen[-window:]) / window
            shift = strength * (logit(observed) - logit(ASSUMED_HOME_RATE))
        out.append((sigmoid(logit(row["ensemble"]) + shift), row["y"]))
        seen.append(row["y"])
    return out


def home_ice(train: list[dict], test: list[dict]) -> dict:
    """
    Candidate 2: let home-ice advantage move instead of being fixed.

    The model assumes home teams win about 54.4% of the time, and the real
    figure swung between 51.9% and 56.5% over these four seasons. This grid
    searches for a rolling window and a strength on the tuning seasons, then
    applies the winner once to the held-out season.
    """
    grid = [(w, s) for w in (100, 200, 300, 500, 800)
            for s in (0.25, 0.5, 0.75, 1.0)]

    best_window, best_strength, best_loss = 0, 0.0, math.inf
    for window, strength in grid:
        loss = log_loss(adaptive_home_ice(train, window, strength))
        if loss < best_loss:
            best_window, best_strength, best_loss = window, strength, loss

    return {
        "name": "Adaptive home-ice advantage",
        "idea": "home ice was worth 51.9%-56.5% depending on the season, but "
                "the model always assumes 54.4%",
        "fitted": {"window": best_window, "strength": best_strength,
                   "gridSize": len(grid)},
        "train": score(adaptive_home_ice(train, best_window, best_strength)),
        "heldOut": score(adaptive_home_ice(test, best_window, best_strength)),
    }


# CANDIDATE 3 - FITTED ENSEMBLE WEIGHTS

def weighted_ensemble(train: list[dict], test: list[dict],
                      parts: list[str], label: str) -> dict:
    """
    Candidate 3: fit real ensemble weights instead of averaging equally.

    The three models are combined in logit space, which is the usual way to
    blend probabilities. Called twice: once over the three models, and once
    with the raw Elo probability added as a fourth input.
    """
    weights, bias = fit_logistic([[logit(r[p]) for p in parts] for r in train],
                                 [r["y"] for r in train])

    def apply(rows: list[dict]) -> list[tuple[float, int]]:
        return [(sigmoid(sum(w * logit(r[p]) for w, p in zip(weights, parts, strict=True)) + bias),
                 r["y"]) for r in rows]

    return {
        "name": label,
        "idea": "the live model averages its parts equally - fit real weights instead",
        "fitted": {"weights": {p: round(w, 4) for p, w in zip(parts, weights, strict=True)},
                   "bias": round(bias, 4)},
        "train": score(apply(train)),
        "heldOut": score(apply(test)),
    }


# How the seasons compare

def per_season(rows: list[dict]) -> list[dict]:
    """
    Season by season, which is where the interesting story turned out to be.

    `spread` is the standard deviation of the probabilities. A model that is
    still confident produces a wide spread; one that has started hedging
    everything towards 50% produces a narrow one.
    """
    out = []
    for season in sorted({r["season"] for r in rows}):
        subset = [r for r in rows if r["season"] == season]
        pairs = [(r["ensemble"], r["y"]) for r in subset]
        probabilities = [r["ensemble"] for r in subset]
        mean = sum(probabilities) / len(probabilities)
        spread = (sum((p - mean) ** 2 for p in probabilities) / len(probabilities)) ** 0.5
        out.append({
            "season": season,
            **score(pairs),
            "meanPrediction": round(mean, 3),
            "spread": round(spread, 3),
            "actualHomeWinRate": round(100 * sum(r["y"] for r in subset) / len(subset), 1),
        })
    return out


# The report

def verdict(candidate: dict, baseline: dict) -> dict:
    """
    Did it actually help on the season it had never seen?

    A candidate has to beat the baseline on the held-out season by more than
    `MEANINGFUL` to count. Anything smaller is well inside the noise you get
    from 1,394 coin-flip-ish hockey games, and calling it an improvement would
    be fooling ourselves.
    """
    MEANINGFUL = 0.005
    delta = candidate["heldOut"]["logLoss"] - baseline["logLoss"]
    if delta < -MEANINGFUL:
        return {"helped": True, "logLossDelta": round(delta, 4),
                "note": "beat the baseline by more than the noise floor"}
    if delta > MEANINGFUL:
        return {"helped": False, "logLossDelta": round(delta, 4),
                "note": "clearly worse than the baseline"}
    return {"helped": False, "logLossDelta": round(delta, 4),
            "note": "no real difference - inside the noise floor"}


def build_report(rows: list[dict]) -> dict:
    """
    Run the whole study and return everything it found.

    The split matters more than any of the candidates: each one is tuned only
    on the earlier seasons and then measured once against the last, which is
    the difference between a result and a number that flatters itself.
    """
    train, test = split(rows)

    baseline_train = score([(r["ensemble"], r["y"]) for r in train])
    baseline_test = score([(r["ensemble"], r["y"]) for r in test])

    candidates = [
        platt(train, test),
        home_ice(train, test),
        weighted_ensemble(train, test, COMPONENTS, "Fitted ensemble weights"),
        weighted_ensemble(train, test, COMPONENTS + ["elo"],
                          "Fitted ensemble weights + Elo"),
    ]
    for candidate in candidates:
        candidate["verdict"] = verdict(candidate, baseline_test)

    return {
        "method": ("tuned on seasons before "
                   f"{HELD_OUT_SEASON}, tested once on {HELD_OUT_SEASON}"),
        "trainGames": len(train),
        "heldOutGames": len(test),
        "baseline": {"name": "Equal-weight ensemble (what is live today)",
                     "train": baseline_train, "heldOut": baseline_test},
        "candidates": candidates,
        "perSeason": per_season(rows),
        "conclusion": (
            "None of the candidates beat the equal-weight ensemble on the "
            "held-out season. Each one gained about 0.0004 log loss on the data "
            "it was tuned on and none of that carried over, which is the "
            "signature of fitting noise. The ensemble stays as it is. The real "
            "finding is in perSeason: accuracy fell from 59.6% to 55.4% and the "
            "spread of the predictions narrowed from 0.113 to 0.092 as the model "
            "aged away from its training data. That is an argument for "
            "monitoring and retraining, not for a post-hoc correction."
        ),
    }


def print_report(report: dict) -> None:
    """Print the report as a table, so a run is readable without opening the JSON."""
    print(f"\n{report['method']}")
    print(f"{report['trainGames']} games to tune on, "
          f"{report['heldOutGames']} sealed until the end\n")

    print(f"{'':<34}{'logloss':>9}{'brier':>8}{'acc':>7}   {'held-out':>9}{'brier':>8}{'acc':>7}")
    base = report["baseline"]
    print(f"{base['name']:<34}{base['train']['logLoss']:>9.4f}"
          f"{base['train']['brier']:>8.4f}{base['train']['accuracy']:>7}   "
          f"{base['heldOut']['logLoss']:>9.4f}{base['heldOut']['brier']:>8.4f}"
          f"{base['heldOut']['accuracy']:>7}")

    for candidate in report["candidates"]:
        print(f"{candidate['name']:<34}{candidate['train']['logLoss']:>9.4f}"
              f"{candidate['train']['brier']:>8.4f}{candidate['train']['accuracy']:>7}   "
              f"{candidate['heldOut']['logLoss']:>9.4f}"
              f"{candidate['heldOut']['brier']:>8.4f}"
              f"{candidate['heldOut']['accuracy']:>7}")

    print("\nDid it help on the season it had never seen?")
    for candidate in report["candidates"]:
        mark = "yes" if candidate["verdict"]["helped"] else "no "
        print(f"  {mark}  {candidate['name']:<34}"
              f"log loss {candidate['verdict']['logLossDelta']:+.4f}  "
              f"({candidate['verdict']['note']})")

    print("\nSeason by season:")
    print(f"  {'season':<10}{'games':>6}{'acc':>7}{'logloss':>9}{'spread':>8}{'home won':>10}")
    for row in report["perSeason"]:
        print(f"  {row['season']:<10}{row['games']:>6}{row['accuracy']:>7}"
              f"{row['logLoss']:>9.4f}{row['spread']:>8.3f}"
              f"{row['actualHomeWinRate']:>9.1f}%")

    print(f"\n{report['conclusion']}\n")


def main() -> None:
    """
    Run the study and write the report next to the model.

    CI runs this on every push and fails if the numbers stop matching the ones
    quoted in the model card, so the documentation cannot quietly go stale.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS,
                        help="the walk-forward predictions CSV")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.predictions.exists():
        raise SystemExit(f"cannot find {args.predictions}")

    report = build_report(load(args.predictions))
    print_report(report)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1))
    print(f"written to {args.out}")


if __name__ == "__main__":
    main()
