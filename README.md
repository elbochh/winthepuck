# WinThePuck

[![CI](https://github.com/elbochh/winthepuck/actions/workflows/ci.yml/badge.svg)](https://github.com/elbochh/winthepuck/actions/workflows/ci.yml)
[![Deploy](https://github.com/elbochh/winthepuck/actions/workflows/deploy-website.yml/badge.svg)](https://github.com/elbochh/winthepuck/actions/workflows/deploy-website.yml)
[![Daily predictions](https://github.com/elbochh/winthepuck/actions/workflows/refresh-predictions.yml/badge.svg)](https://github.com/elbochh/winthepuck/actions/workflows/refresh-predictions.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-189%20passing-brightgreen.svg)](#tests)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg)](#tests)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![mypy](https://img.shields.io/badge/types-mypy-blue.svg)](https://mypy-lang.org/)

**A machine learning model that predicts NHL games, and a website that shows you
how often it gets them wrong.**

🏒 **[winthepuck.azurewebsites.net](https://winthepuck.azurewebsites.net)** ·
📊 [Model health](https://winthepuck.azurewebsites.net/monitoring) ·
📄 [Architecture](docs/ARCHITECTURE.md) ·
🧠 [Model card](docs/MODEL_CARD.md)

## Why I built it

I wanted to know whether I could actually predict a hockey game, and I wanted to
do it the whole way. Not a notebook with a nice accuracy score at the bottom, but
a real thing running on the internet that keeps making predictions whether I am
watching or not.

So it pulls 15 seasons out of the NHL's public API, builds 127 features per game,
trains an ensemble, and puts the results on a site anyone can open. Every morning
a job wakes up, works out the probabilities for the next two weeks of games, and
posts them to the site. It has been doing that on its own since August.

The part I did not expect to spend the most time on was **finding out my model
was slowly getting worse**. That turned out to be the most interesting thing in
the project, and most of what I learned is in the two documents linked above.

## How good is it, honestly?

**58.6% accurate** over 5,592 games it had never seen.

That sounds unimpressive until you know the numbers around it. Published research
puts the ceiling for single-game NHL prediction near **62%**. Bookmakers, with far
more information than I have, land at **59% to 60%**. Hockey is low scoring and
about a third of games turn on one bounce. That is the sport, not the model.

| | | |
|---|---|---|
| **58.6%** | accuracy | over 5,592 out-of-sample games |
| **0.6662** | log loss | against 0.6931 for always guessing 50% |
| **65.4%** | accuracy | on the 2,356 games it was most confident about |
| **1.31** | calibration error | when it says 70%, roughly 70% happens |

Tested **walk-forward**: to predict a given month, the model may only learn from
games that finished before that month started. It never sees the answer to a game
it is being asked about. A random train/test split would have let it learn from
March to predict January, and it would have looked much better than it really is.

And the uncomfortable bit, which I would rather say myself: **the three-model
ensemble barely beats a plain logistic regression**, and most of the signal is in
the Elo rating. The other 120 or so features are worth about one accuracy point
between them.

## The interesting part: the model is ageing

When I broke the test down by season, this fell out:

| Season | Accuracy | Spread of predictions |
|---|---|---|
| 2022/23 | 59.6% | 0.113 |
| 2023/24 | 61.1% | 0.118 |
| 2024/25 | 58.3% | 0.106 |
| 2025/26 | **55.4%** | **0.092** |

Two things moving together. It is getting less accurate, *and* its probabilities
are bunching towards 50%, which means it is hedging. That is what a model
drifting away from its training data looks like.

That pattern usually means over-confidence, and there are standard fixes for it.
I tried three ideas, in four variants. Each was tuned on the first three seasons
and then run **once** against a fourth I had not touched.

| What I tried | Log loss change on held-out data | Shipped? |
|---|---|---|
| Platt scaling | +0.0005 | No |
| Adaptive home-ice advantage | −0.0003 | No |
| Fitted ensemble weights | −0.0004 | No |
| Fitted ensemble weights plus Elo | −0.0002 | No |

Every one of them improved the data it was tuned on by about 0.0004 and none of
it survived. On 1,394 games that is noise, so I shipped none of them.

What that told me is that the problem was never calibration. The model has aged,
and you cannot patch that after the fact. So instead of a correction I built the
thing that **detects** it: a
[monitoring page](https://winthepuck.azurewebsites.net/monitoring) that recomputes
calibration, prediction drift (PSI) and live accuracy from the database on every
load. The honest recommendation is to retrain.

The whole experiment reruns in about 30 seconds, and CI fails if its numbers ever
drift from what the model card claims:

```bash
cd model && python3 evaluate_model.py
```

## How it is built

The site runs on Azure's **free tier**, which gives it 1 GB of memory.
scikit-learn and CatBoost together are bigger than the entire Flask app, so the
model simply does not fit next to the website.

So it does not live there:

```
   NHL public API              GitHub Actions                    Azure
  (free, no API key)      (free runner, once a day)        (free F1 tier)
        │                        │                               │
        │  schedules, scores     │                               │
        └───────────────────────>│                               │
                                 │  trained model + Elo state    │
                                 │  ──> 14 days of predictions   │
                                 │                               │
                                 │   POST /api/admin/refresh     │
                                 └──────────────────────────────>│
                                                                 │
                                                         Flask + SQLite
                                                      accounts · picks
                                                   comments · monitoring
                                                                 │
                                                                 ▼
                                              winthepuck.azurewebsites.net
```

This is **batch inference**: predictions are computed on a schedule and written
somewhere the app reads them. A prediction here is good for a day, so recomputing
it on every request would be waste rather than freshness. It also means the
website needs exactly three dependencies and starts in under a second.

There is more on the trade-offs, and on two bugs worth reading about, in
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## What is in here

```
web/         The Flask site that is deployed. Pages, accounts, picks,
             comments, leaderboard, and the model-health page.
model/       The daily prediction job and the trained model it loads.
             Also evaluate_model.py, the experiment above.
frontend/    A second interface in Next.js 16 / React 19 / TypeScript:
             the same predictions, plus an in-game win probability replay.
ml/          How the model was built. Feature engineering, training,
             walk-forward evaluation, and the in-game model.
pipeline/    The data collection layer. Pulls schedules, box scores,
             play-by-play and shift charts from the NHL API.
docs/        Architecture and the model card.
```

**Stack:** Python · Flask · SQLite · scikit-learn · CatBoost · NumPy · pandas ·
TypeScript · React · Next.js · Tailwind · Docker · GitHub Actions · Azure ·
pytest · ruff · mypy

## Running it

The quickest way, with nothing installed but Docker:

```bash
docker compose up --build
```

Then open <http://localhost:8000>. Sign in as `demo` / `puck1234`, or register.

To run the prediction job against it:

```bash
docker compose run --rm refresh
```

Without Docker:

```bash
cd web
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The database builds itself from the files in `web/data/` the first time it
starts. There is no setup script to remember, which is the only reason it can run
on a host where nobody can log in and run a migration.

The React front end is separate:

```bash
cd frontend && npm install && npm run dev
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                    # 189 tests
pytest -m "not slow"      # skip the evaluation study, about 2 seconds
pytest --cov              # 85% coverage
ruff check . && mypy web model
```

The tests I would actually point at are the ones guarding failures that are
completely silent otherwise:

- A team's recent form must never include the game being predicted. That is the
  leak that makes a model look brilliant in testing and fall apart live.
- Elo ratings stay zero-sum, so the league total cannot drift.
- All 127 features reach the model. This one found a real bug. One feature had
  been silently missing from **every prediction the site had ever made**, quietly
  filled in with the training average by an imputer. Nothing had ever errored.
- A transient NHL API outage does not take the daily job down. That one is a
  regression test, because it happened.

CI runs everything on every push, on Python 3.12 and 3.13, and separately builds
both Docker images and checks that the site actually answers.

## What I would do next

- **Retrain on the finished 2025/26 season.** The evidence above says this is the
  single most valuable change available, and nothing else comes close.
- **Feed in goalie confirmations.** The starting goalie is usually announced an
  hour before the game and is probably the biggest thing the model ignores.
- **Version the model artefact.** Right now it is a joblib file with no training
  date or commit hash in it, so I cannot say with certainty which model produced
  a given historical prediction.
- **Track feature-level drift, not just prediction drift.** I can see the output
  distribution moving. I cannot yet see which input caused it.

## Where the data comes from

Everything comes from the NHL's own public API (`api-web.nhle.com` and
`api.nhle.com`), which is free and needs no key and no account. Every win
probability, confidence figure and set of odds is produced by the model in this
repository.

The odds shown are the **fair** odds implied by the model's probability, with no
bookmaker margin added. They are a restatement of the probability, not an edge.
This does not beat the closing line and is not built to. **It is not betting
advice.**

Team crests are served from the NHL's asset host and remain the property of the
NHL and its clubs.
