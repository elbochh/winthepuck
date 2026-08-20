# WinThePuck — NHL Winner Prediction

A student project that predicts who will win an NHL hockey game, and puts those
predictions on a website anybody can use.

**Live site:** https://winthepuck.azurewebsites.net

Every number on the site is real. The schedules, scores and team stats come from
the NHL's own public API, and every win probability is produced by a model we
trained ourselves on 20,591 completed games.

---

## What the model actually does

We tested the model the honest way — *walk-forward*. To predict the games in a
given month, the model is only allowed to learn from games that finished before
that month started. It never sees the answer to a game it is being asked about.

Measured that way, across 4 seasons and 5,592 games:

| Model | Accuracy | Log loss |
|---|---|---|
| **WinThePuck ensemble** | **58.6%** | 0.6662 |
| Logistic regression | 58.6% | 0.6665 |
| CatBoost | 58.4% | 0.6680 |
| Gradient boosting | 58.2% | 0.6687 |
| Elo rating only | 57.6% | 0.6726 |

On the 2,356 games the model was most confident about, it was right **65.4%** of
the time. For context, published research puts the ceiling for single-game NHL
prediction near 62%, and bookmakers' closing lines land around 59–60%. Hockey is
genuinely hard to predict — a third of games are decided by one bounce.

---

## The five phases

| Phase | Folder | What it is |
|---|---|---|
| 1 — Data | `nhl_data_pipeline/` | Downloads 15 seasons from the NHL API: schedules, box scores, play-by-play, shift charts. |
| 2 — Model | `nhl_model/` | Builds the features, trains the ensemble, runs the walk-forward test. |
| 3 — Front end | `Phase 3/winthepuck-website/` | The first version of the site, HTML/CSS/JavaScript only. |
| 4 — Back end | `Phase 4/winthepuck-backend/` | Flask and SQLite: accounts, picks, comments, leaderboard. |
| 5 — Cloud | `Phase 5/` | The real-data version, deployed to Microsoft Azure. |

---

## Phase 5 in one picture

```
   NHL public API                GitHub Actions                   Azure
  (free, no key)          (free runner, once a day)        (free F1 App Service)
        │                          │                              │
        │  schedules, scores       │                              │
        └─────────────────────────>│                              │
                                   │  trained model + Elo state   │
                                   │  ──> 30 days of predictions  │
                                   │                              │
                                   │  POST /api/admin/refresh     │
                                   └─────────────────────────────>│
                                                                  │
                                                          Flask + SQLite
                                                       accounts, picks,
                                                       comments, leaderboard
                                                                  │
                                                                  v
                                                    https://winthepuck.azurewebsites.net
```

The heavy machine learning stays out of the website. The site itself only needs
Flask, so it fits comfortably in Azure's free tier; the model runs once a day on
a GitHub runner and posts its answers in.

### Phase 5 folders

- `Phase 5/winthepuck-cloud/` — the Flask website that runs on Azure
- `Phase 5/model-service/` — the prediction service and the daily refresh job
- `Phase 5/docs/` — the deployment write-up and the progress report
- `.github/workflows/` — deploy the site, and refresh the predictions daily

---

## Running the website on your own machine

```bash
cd "Phase 5/winthepuck-cloud"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The database builds itself from the files in `data/`
the first time you start it — there is no setup script to remember.

Sign in as `demo` / `puck1234`, or create your own account.

## Refreshing the predictions by hand

```bash
cd "Phase 5/model-service"
pip install -r requirements.txt
python3 refresh_predictions.py --out refresh_payload.json
```

Add `--post https://winthepuck.azurewebsites.net --token <token>` to send the
result to the live site.

## Retraining the model

Only needed when the season's data has been refreshed. It needs the Phase 1
pipeline output, so it has to run on a machine that has the full dataset.

```bash
cd "Phase 5/model-service"
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

Team crests are served from the NHL's own asset host and are the property of the
NHL and its clubs. This is a student project for coursework, not a commercial
product, and nothing here is betting advice.
