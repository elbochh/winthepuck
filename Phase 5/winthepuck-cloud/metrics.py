"""Scoring the model against reality: calibration, drift and live performance.

A model that is right 58% of the time is not automatically a *good* model. Two
questions matter just as much, and this module answers both:

  Is it honest?   When the model says "70%", does that team really win about
                  70% of the time? A model can be accurate and still lie about
                  how sure it is. That is what calibration measures.

  Has it drifted? The model was trained on games up to June 2026. Hockey moves
                  on - rules change, teams rebuild. If the shape of today's
                  predictions stops looking like the shape of the predictions
                  it made during testing, that is a warning worth showing.

Everything here is plain Python on purpose. The website runs on the free Azure
tier, where numpy and pandas would not fit, so these are written out longhand.
They are also pure functions - no database, no network - which is what makes
them easy to test.

The maths is standard:
  Brier score  - mean squared error of a probability   (lower is better)
  Log loss     - the same idea, but punishes confident mistakes harder
  ECE          - expected calibration error, the average gap between how sure
                 the model was and how often it was actually right
  PSI          - population stability index, the usual industry measure of how
                 far a distribution has moved from its baseline
"""
from __future__ import annotations

import math

# How PSI is read in industry. These thresholds come from credit-risk
# scorecard practice, where PSI has been the standard drift measure for years.
PSI_STABLE = 0.10
PSI_MODERATE = 0.25

# Below this many settled games, any metric we print is mostly noise, so the
# website says "not enough games yet" instead of showing a number nobody
# should trust.
MIN_SAMPLE = 30

# PSI is a comparison of two histograms, so it needs enough observations to
# fill the buckets before its value means much. Below MIN_DRIFT_SAMPLE we
# refuse to compute it at all; below DRIFT_CONFIDENT_SAMPLE we compute it but
# label the answer provisional, because a couple of nights of hockey can move
# it on their own.
MIN_DRIFT_SAMPLE = 30
DRIFT_CONFIDENT_SAMPLE = 100

# Probabilities are squeezed into this range before taking a logarithm, so a
# confident miss costs a large number instead of infinity.
EPSILON = 1e-15


# ===========================================================
# THE PAIRS EVERYTHING IS BUILT FROM
# ===========================================================
#
# Every function below takes the same thing: a list of (probability, outcome)
# pairs, where probability is the chance the model gave the home team as a
# number between 0 and 1, and outcome is 1 if the home team really won.


def _clamp(probability: float) -> float:
    return min(max(probability, EPSILON), 1 - EPSILON)


def accuracy(pairs: list[tuple[float, int]]) -> float | None:
    """How often the model's pick was the team that actually won, as a %."""
    if not pairs:
        return None
    hits = sum(1 for probability, outcome in pairs
               if (probability >= 0.5) == (outcome == 1))
    return round(100 * hits / len(pairs), 1)


def brier_score(pairs: list[tuple[float, int]]) -> float | None:
    """
    Mean squared error of the probabilities. 0 is perfect, 0.25 is a coin flip.

    This is the single fairest number for a forecaster, because it rewards
    being right *and* being honest about how right you expected to be.
    """
    if not pairs:
        return None
    total = sum((probability - outcome) ** 2 for probability, outcome in pairs)
    return round(total / len(pairs), 4)


def log_loss(pairs: list[tuple[float, int]]) -> float | None:
    """
    The same idea as Brier, but a confident wrong answer hurts much more.

    ln(2) = 0.693 is what you score by saying "50%" to everything, so anything
    below 0.693 means the model is genuinely adding information.
    """
    if not pairs:
        return None
    total = 0.0
    for probability, outcome in pairs:
        probability = _clamp(probability)
        total -= (math.log(probability) if outcome == 1
                  else math.log(1 - probability))
    return round(total / len(pairs), 4)


def baseline_log_loss() -> float:
    """What log loss you get by refusing to commit and saying 50% every time."""
    return round(-math.log(0.5), 4)


# ===========================================================
# CALIBRATION - IS THE MODEL HONEST ABOUT HOW SURE IT IS?
# ===========================================================

def reliability_curve(pairs: list[tuple[float, int]],
                      bins: int = 10) -> list[dict]:
    """
    Group the predictions by how confident they were, and check each group.

    A perfectly calibrated model produces a table where `predicted` and
    `actual` match all the way down: of the games it called at 70%, about 70%
    were won. Plotting the two against each other is the reliability diagram
    the /monitoring page draws.

    Predictions are folded onto the confidence scale first - saying "the home
    team has a 20% chance" is the same statement as "the away team has 80%",
    so both land in the 80% bucket.
    """
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]

    for probability, outcome in pairs:
        # fold onto 0.5 - 1.0: how sure the model was about its own pick
        picked_home = probability >= 0.5
        confidence = probability if picked_home else 1 - probability
        was_right = 1 if picked_home == (outcome == 1) else 0

        index = int((confidence - 0.5) / 0.5 * bins)
        index = min(max(index, 0), bins - 1)
        buckets[index].append((confidence, was_right))

    curve = []
    for index, bucket in enumerate(buckets):
        low = 50 + index * (50 / bins)
        high = low + (50 / bins)
        if not bucket:
            curve.append({
                "range": f"{low:.0f}-{high:.0f}%", "games": 0,
                "predicted": None, "actual": None, "gap": None,
            })
            continue
        predicted = 100 * sum(c for c, _ in bucket) / len(bucket)
        actual = 100 * sum(r for _, r in bucket) / len(bucket)
        curve.append({
            "range": f"{low:.0f}-{high:.0f}%",
            "games": len(bucket),
            "predicted": round(predicted, 1),
            "actual": round(actual, 1),
            "gap": round(actual - predicted, 1),
        })
    return curve


def expected_calibration_error(pairs: list[tuple[float, int]],
                               bins: int = 10) -> float | None:
    """
    One number for the whole reliability table: the average gap, in points.

    Each bucket contributes its own gap between predicted and actual, weighted
    by how many games are in it. An ECE of 2.0 means the model's stated
    confidence is out by about two percentage points on average - which for a
    sports model is good.
    """
    if not pairs:
        return None
    curve = reliability_curve(pairs, bins)
    played = sum(row["games"] for row in curve)
    if played == 0:
        return None
    weighted = sum(row["games"] * abs(row["gap"])
                   for row in curve if row["gap"] is not None)
    return round(weighted / played, 2)


# ===========================================================
# DRIFT - HAS THE WORLD MOVED SINCE TRAINING?
# ===========================================================

def distribution(probabilities: list[float], edges: list[float]) -> list[float]:
    """What share of the predictions falls into each band."""
    if not probabilities:
        return [0.0] * (len(edges) - 1)
    counts = [0] * (len(edges) - 1)
    for probability in probabilities:
        for index in range(len(edges) - 1):
            upper = edges[index + 1]
            last = index == len(edges) - 2
            if probability >= edges[index] and (probability < upper or last):
                counts[index] += 1
                break
    total = sum(counts)
    return [count / total for count in counts] if total else [0.0] * len(counts)


def population_stability_index(reference: list[float],
                               current: list[float],
                               edges: list[float] | None = None) -> float | None:
    """
    How far today's predictions have moved from the ones made during testing.

    PSI compares two histograms bucket by bucket. It is the measure most
    monitoring tools reach for, and it is read like this:

        under 0.10   no real change - carry on
        0.10 - 0.25  something has moved, worth watching
        over 0.25    the live data no longer looks like the test data

    What this catches for us is *prediction drift*: the model quietly starting
    to hand out much bolder, or much more timid, probabilities than it used to.
    That usually means the inputs feeding it have shifted underneath.
    """
    if not reference or not current:
        return None
    edges = edges or [0.0, 0.35, 0.45, 0.5, 0.55, 0.65, 1.0]

    expected = distribution(reference, edges)
    actual = distribution(current, edges)

    # An empty bucket makes the logarithm blow up, so give it a floor small
    # enough not to matter and large enough to stay finite. This is the usual
    # convention rather than something we invented.
    floor = 0.5 / max(len(reference), len(current))

    psi = 0.0
    for share_expected, share_actual in zip(expected, actual, strict=True):
        share_expected = max(share_expected, floor)
        share_actual = max(share_actual, floor)
        psi += (share_actual - share_expected) * math.log(share_actual / share_expected)
    return round(psi, 4)


def drift_verdict(psi: float | None) -> str:
    """Turn a PSI number into the word shown on the page."""
    if psi is None:
        return "unknown"
    if psi < PSI_STABLE:
        return "stable"
    if psi < PSI_MODERATE:
        return "watch"
    return "shifted"


def drift_report(reference: list[float], current: list[float]) -> dict:
    """
    PSI plus an honest note on whether the sample is big enough to trust it.

    Two things can move this number, and only one of them is interesting. A
    genuine shift in the model's behaviour is worth acting on. A quiet week
    with nine games on the schedule is not, and without this guard the page
    would announce a crisis every time the slate got short.
    """
    if len(current) < MIN_DRIFT_SAMPLE or len(reference) < MIN_DRIFT_SAMPLE:
        return {
            "psi": None,
            "verdict": "unknown",
            "provisional": True,
            "referenceGames": len(reference),
            "currentGames": len(current),
            "note": (f"needs at least {MIN_DRIFT_SAMPLE} games on both sides "
                     "before the comparison means anything"),
        }

    psi = population_stability_index(reference, current)
    provisional = len(current) < DRIFT_CONFIDENT_SAMPLE
    return {
        "psi": psi,
        "verdict": drift_verdict(psi),
        "provisional": provisional,
        "referenceGames": len(reference),
        "currentGames": len(current),
        "note": (f"based on only {len(current)} games, so treat it as a hint "
                 f"rather than a verdict - it settles down past "
                 f"{DRIFT_CONFIDENT_SAMPLE}"
                 if provisional else
                 f"based on {len(current)} games"),
    }


# ===========================================================
# PUTTING IT TOGETHER
# ===========================================================

def summarise(pairs: list[tuple[float, int]], bins: int = 10) -> dict:
    """Every calibration number for one set of graded predictions."""
    if len(pairs) < MIN_SAMPLE:
        return {
            "games": len(pairs),
            "enough": False,
            "needed": MIN_SAMPLE,
        }
    return {
        "games": len(pairs),
        "enough": True,
        "accuracy": accuracy(pairs),
        "brier": brier_score(pairs),
        "logLoss": log_loss(pairs),
        "baselineLogLoss": baseline_log_loss(),
        "ece": expected_calibration_error(pairs, bins),
        "reliability": reliability_curve(pairs, bins),
    }


def compare(live: dict, reference: dict, tolerance: float = 5.0) -> dict:
    """
    Live model against its own test-set track record.

    `tolerance` is how many accuracy points the live figure is allowed to slip
    before we call it a regression. Hockey is noisy and a few weeks of games is
    a small sample, so the bar is deliberately generous - the point is to catch
    a model that has genuinely stopped working, not to panic over a bad week.
    """
    if not live.get("enough") or not reference.get("enough"):
        return {"status": "warming-up", "delta": None}

    delta = round(live["accuracy"] - reference["accuracy"], 1)
    if delta < -tolerance:
        status = "below-baseline"
    elif delta > tolerance:
        status = "above-baseline"
    else:
        status = "on-track"
    return {"status": status, "delta": delta, "tolerance": tolerance}
