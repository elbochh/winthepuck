# WinThePuck — NHL win prediction, end to end

[![CI](https://github.com/elbochh/winthepuck/actions/workflows/ci.yml/badge.svg)](https://github.com/elbochh/winthepuck/actions/workflows/ci.yml)
[![Deploy](https://github.com/elbochh/winthepuck/actions/workflows/deploy-website.yml/badge.svg)](https://github.com/elbochh/winthepuck/actions/workflows/deploy-website.yml)
[![Daily predictions](https://github.com/elbochh/winthepuck/actions/workflows/refresh-predictions.yml/badge.svg)](https://github.com/elbochh/winthepuck/actions/workflows/refresh-predictions.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-186%20passing-brightgreen.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-82%25-brightgreen.svg)](#testing)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![Checked with mypy](https://img.shields.io/badge/types-mypy-blue.svg)](https://mypy-lang.org/)

Predicts who will win an NHL game, and puts those predictions on a website
anybody can use. A machine learning model trained on 20,591 real games, a
Flask site on Azure, and a daily job that keeps the two in step — with
monitoring that keeps checking whether the model is still any good.

**Live site:** <https://winthepuck.azurewebsites.net>
**Model health:** <https://winthepuck.azurewebsites.net/monitoring>

Every number on the site is real. Schedules, scores and team stats come from
the NHL's own public API; every win probability comes from the model.

---

## Built with

**Machine learning** · scikit-learn · CatBoost · NumPy · pandas · soft-voting ensemble · Elo ratings · walk-forward validation · calibration (Brier, log loss, ECE) · drift detection (PSI)

**Back end** · Python 3.12 · Flask · SQLite (WAL) · gunicorn · REST/JSON API

**Front end** · HTML · CSS · vanilla JavaScript · Jinja2 · responsive, no framework

**Platform** · Docker · Docker Compose · GitHub Actions (CI/CD) · Microsoft Azure App Service

**Quality** · pytest · pytest-cov · ruff · mypy · 186 tests · 82% coverage

---

## What the model does

Tested **walk-forward**, which is the only honest way to test something that
predicts the future: to predict the games in a given month, the model may only
learn from games that finished before that month started. It never sees the
answer to a game it is being asked about.

Across 4 seasons and 5,592 games:

| Model | Accuracy | Log loss |
|---|---|---|
| **WinThePuck ensemble** | **58.6%** | **0.6662** |
| Logistic regression | 58.6% | 0.6665 |
| CatBoost | 58.4% | 0.6680 |
| Gradient boosting | 58.2% | 0.6687 |
| Elo rating only | 57.6% | 0.6726 |

On the 2,356 games it was most confident about, it was right **65.4%** of the
time, and its calibration error across all 5,592 games is **1.31 points** —
when it says 70%, roughly 70% happens.

For context: published research puts the ceiling for single-game NHL
prediction near 62%, and bookmakers' closing lines land around 59–60%. A third
of NHL games are decided by one bounce.

Full details, known weaknesses and three rejected improvements:
**[MODEL_CARD.md](Phase%205/model-service/MODEL_CARD.md)**

---

## How it fits together

The site runs on Azure's **free tier**, where scikit-learn and CatBoost do not
fit. So the model never runs on the web server:

```
   NHL public API                GitHub Actions                   Azure
  (free, no key)          (free runner, once a day)        (free F1 App Service)
        │                          │                              │
        │  schedules, scores       │                              │
        └─────────────────────────>│                              │
                                   │  trained model + Elo state   │
                                   │  ──> 14 days of predictions  │
                                   │                              │
                                   │  POST /api/admin/refresh     │
                                   └─────────────────────────────>│
                                                                  │
                                                          Flask + SQLite
                                                       accounts, picks,
                                                    comments, monitoring
                                                                  │
                                                                  v
                                                    https://winthepuck.azurewebsites.net
```

This is batch inference: predictions are useful for a day, so recomputing them
per request would be waste rather than freshness. The website needs only
Flask, Werkzeug and gunicorn.

Full write-up, including the trade-offs and two bugs worth reading about:
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

---

## Watching the model age

A published accuracy figure is a photograph. Over four seasons this model's
accuracy fell from 59.6% to 55.4% while the spread of its predictions narrowed
from 0.113 to 0.092 — it was quietly hedging towards 50% as it drifted away
from its training data.

Three standard corrections were tested for that — Platt scaling, an adaptive
home-ice term, and fitted ensemble weights — each tuned on the first three
seasons and applied **once** to a fourth that was never looked at until the
final table. All three gained about 0.0004 log loss where they were tuned and
none of it survived. That is the signature of fitting noise, so none shipped.

What shipped instead was the measurement. `/monitoring` recomputes calibration,
prediction drift (PSI) and live accuracy from the database, with guards so it
does not cry wolf on a quiet week. The experiment is reproducible:

```bash
cd "Phase 5/model-service" && python3 evaluate_model.py
```

---

## The five phases

| Phase | Folder | What it is |
|---|---|---|
| 1 — Data | `nhl_data_pipeline/` | Downloads 15 seasons from the NHL API: schedules, box scores, play-by-play, shift charts (~18 GB). |
| 2 — Model | `nhl_model/` | Builds 127 features per game, trains the ensemble, runs the walk-forward test. |
| 3 — Front end | `Phase 3/winthepuck-website/` | The first version of the site, HTML/CSS/JavaScript only. |
| 4 — Back end | `Phase 4/winthepuck-backend/` | Flask and SQLite: accounts, picks, comments, leaderboard. |
| 5 — Cloud | `Phase 5/` | Real data end to end, deployed to Azure, with CI, containers and monitoring. |

---

## Running it

**With Docker** — nothing else to install:

```bash
cd "Phase 5"
docker compose up --build
```

Then open <http://localhost:8000>. To run the prediction job against it:

```bash
docker compose run --rm refresh
```

**Without Docker:**

```bash
cd "Phase 5/winthepuck-cloud"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. The database builds itself from the files in
`data/` the first time it starts — there is no setup script to remember.

Sign in as `demo` / `puck1234`, or create an account.

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest                        # 186 tests
pytest -m "not slow"          # skip the evaluation study (~2 seconds)
pytest --cov                  # with coverage
ruff check .                  # lint
mypy "Phase 5"                # types
```

The tests worth reading are the ones guarding failures that would otherwise be
silent: that a team's recent form never includes the game being predicted,
that Elo ratings stay zero-sum, that all 127 features reach the model, and
that a transient NHL API outage no longer takes the daily job down.

CI runs all of it on every push, on Python 3.12 and 3.13, plus a job that
builds both Docker images and checks the site really answers.

---

## Refreshing the predictions by hand

```bash
cd "Phase 5/model-service"
pip install -r requirements.txt
python3 refresh_predictions.py --out refresh_payload.json
```

Add `--post https://winthepuck.azurewebsites.net --token <token>` to send the
result to the live site.

## Retraining

Only needed once a season's data is complete. It needs the Phase 1 pipeline
output, so it has to run on a machine with the full dataset.

```bash
cd "Phase 5/model-service"
pip install -r requirements-training.txt
python3 build_serving_bundle.py     # retrains and rewrites serving/
python3 export_history.py           # re-exports the finished season
```

---

## Where the data comes from

- **NHL public API** — `api-web.nhle.com` and `api.nhle.com`. Free, no API key,
  no account. Schedules, scores, standings and team season stats.
- **Our own model** — every win probability, confidence figure and set of odds.
  The odds shown are the *fair* odds implied by our probability, with no
  bookmaker margin added, so they are not a betting recommendation.

Team crests are served from the NHL's own asset host and are the property of
the NHL and its clubs. This is a student project for coursework, not a
commercial product, and nothing here is betting advice.
