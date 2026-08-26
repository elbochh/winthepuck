# Architecture

How WinThePuck is put together, and why it is put together that way. Most of
this document is about trade-offs rather than components — the shape of the
system is mostly a consequence of one constraint, described below.

---

## 1. The constraint that decided everything

The site runs on Azure App Service's **free F1 tier**: 1 GB of memory, 1 GB of
disk, no scaling, and a worker that goes to sleep when nobody is using it.

The model does not fit. scikit-learn, CatBoost and NumPy together are larger
than the entire Flask application, and loading three trained models into an F1
worker leaves nothing for serving pages.

The obvious answer — pay for a bigger tier — was not available. The answer
that was available is the one the system is built around:

> **The model never runs on the web server. It runs somewhere else, on a
> schedule, and posts its answers in.**

Once that decision is made, everything else follows. The website becomes a
small Flask app with three dependencies. The heavy machine learning becomes a
batch job on a free GitHub Actions runner. The two only ever meet through one
authenticated HTTP endpoint.

This is a real pattern, not a workaround. It is how most prediction systems
that do not need sub-second freshness are built: **batch inference**, written
to a store the application reads. Predictions here are useful for a day, so
recomputing them per request would be waste, not freshness.

---

## 2. The shape of it

```
┌──────────────────────┐
│   NHL public API     │   free, no key, no account
│   api-web.nhle.com   │   schedules · scores · standings · club stats
└──────────┬───────────┘
           │
           │  (1) once a day, 11:30 UTC
           ▼
┌──────────────────────────────────────────────┐
│  GitHub Actions runner    (free, ephemeral)  │
│                                              │
│   refresh_predictions.py                     │
│     · download every game of the season      │
│     · move Elo ratings forward on results    │
│     · rebuild recent-form features           │
│     · run 3 trained models, average them     │
│     · price fair odds from the probability   │
└──────────┬───────────────────────────────────┘
           │
           │  (2) POST /api/admin/refresh
           │      Bearer token · ~30 KB of JSON
           ▼
┌──────────────────────────────────────────────┐
│  Azure App Service — free F1 tier            │
│                                              │
│   gunicorn → Flask                           │
│     · 8 pages, 5 JSON endpoints              │
│     · accounts, picks, comments, leaderboard │
│     · calibration + drift monitoring         │
│                                              │
│   SQLite on /home  (survives redeploys)      │
└──────────┬───────────────────────────────────┘
           │
           ▼
   https://winthepuck.azurewebsites.net
```

Three processes, each doing one job, connected by one authenticated endpoint
and one database.

---

## 3. The layers

Five directories, each a working piece on its own, arranged roughly in the
order data flows through them.

| Directory | What it does |
|---|---|
| `pipeline/` | Collects the raw data. Downloads 15 seasons from the NHL API: schedules, box scores, play-by-play, shift charts. About 18 GB on disk, none of it in this repository. |
| `ml/` | Turns that into a model. Builds 127 features per game, trains the ensemble, runs the walk-forward test, and trains the separate in-game win-probability model. |
| `model/` | Serves the model. The trained bundle, the daily prediction job, and the evaluation study. Deployed to a GitHub Actions runner. |
| `web/` | The Flask site that is actually deployed. Pages, accounts, picks, comments, leaderboard, monitoring. |
| `frontend/` | A second interface in Next.js and TypeScript, reading the same exported data. |

The split between `ml/` and `model/` is the important one and it is not
cosmetic: `ml/` needs pandas and the full 18 GB dataset and runs on a laptop,
while `model/` only ever loads an already-trained bundle and runs in the cloud
in about a minute. Keeping them apart is what makes the daily job cheap enough
to run on a free runner.

---

## 4. The prediction job

`model/` — runs on a GitHub Actions runner, finishes in about
a minute.

### What it does each night

1. **Download the season.** One request per club, 32 in total, deduplicated by
   game id.
2. **Catch the ratings up.** Every game that finished since the last run is
   replayed through the Elo update. The saved state records the date it is
   accurate to, which is what stops a game being applied twice — the job
   downloads the whole season every night, most of which it has already seen.
3. **Rebuild recent form.** Last-5 and last-10 records, home and road splits,
   rest days, head-to-head — all recomputed from real scores, all using only
   games that finished before the game being predicted.
4. **Predict.** Assemble 127 features per upcoming game, run all three models,
   average the probabilities.
5. **Price it.** Convert the probability to fair American odds with no
   bookmaker margin.
6. **Post it.** One JSON payload to the website.

### Why the ratings are replayed rather than stored per game

`team_state.json` holds each club's current Elo and decayed form, plus the
date it is accurate to. That is a few kilobytes instead of a database, and it
means the job is **idempotent**: re-running it after a failure produces the
same answer, because the cut-off date decides what gets applied rather than
whether the job has run before.

This is directly tested — see `test_running_twice_changes_nothing_the_second_time`.

### Why some features are frozen

The box-score features (hits, blocked shots, goalie save percentage) need the
full full 18 GB dataset, which cannot live on a free runner. Those are
carried in `team_state.json` from the last full retrain and stay fixed between
retrains.

Everything a final score can tell you — form, splits, rest, head-to-head, Elo
— is recomputed fresh every night. That is roughly two thirds of the features
moving daily and one third frozen, which is a deliberate and documented
trade-off rather than an oversight.

---

## 5. The website

`web/` — Flask, SQLite, and three dependencies.

```
app.py          routes: 8 pages, 5 JSON endpoints
database.py     connection handling, one place that talks to SQLite
nhl_data.py     turning a refresh payload into database rows
scoring.py      leaderboard points and streaks
metrics.py      calibration and drift maths (pure functions, no I/O)
monitoring.py   which games count as baseline and which as live
security.py     response headers and rate limiting
config.py       settings, read from the environment
schema.sql      the tables
```

### The database builds itself

There is no setup script. On first start the app notices the tables are
missing and builds them from the JSON files in `data/`. That is what makes it
deployable to a platform where nobody can log in to a server and run a
migration.

Azure starts **two gunicorn workers at once**, so both could try to build the
database simultaneously. A lock file settles it: whichever worker creates it
does the building, and the other waits up to a minute for the tables to
appear.

### Where the database lives

Azure gives every site a `/home` directory that survives restarts and
redeploys. The database is written there rather than next to the code, which
is why members and their comments are not wiped every time the site is
deployed.

SQLite runs in **WAL mode**, so somebody can read a page while the nightly
refresh is writing.

### The one write endpoint

`POST /api/admin/refresh` is the only way data gets in. It requires a bearer
token compared with `secrets.compare_digest`, is rate limited, and rejects
anything that does not look like a payload. Without the token configured, the
route returns 503 rather than being open.

---

## 6. Monitoring

A published accuracy figure is a photograph. The model card explains why that
is not enough here: over four seasons this model's accuracy fell from 59.6% to
55.4% while its predictions bunched towards 50%.

`/monitoring` recomputes three things from the database on every load:

- **Calibration** — Brier score, log loss, and expected calibration error,
  with the reliability table behind them. Answers "when it says 70%, does 70%
  happen?"
- **Prediction drift** — population stability index between the spread of
  today's predictions and the spread during testing. Under 0.10 is normal, over
  0.25 means retraining is due.
- **Live accuracy** — games this deployment predicted itself, compared with
  the walk-forward baseline.

Two guards keep it honest. Nothing is shown below 30 settled games, and a PSI
computed from a short slate is labelled provisional. A monitoring page that
cries wolf on a quiet week is a monitoring page people stop reading.

The maths is in `metrics.py` — pure functions, no database, no network, which
is what lets it be tested against cases where the right answer is known in
advance: a perfect forecaster, a useless one, a liar.

---

## 7. Continuous integration

Four workflows' worth of checks, in `.github/workflows/`:

| Workflow | When | What |
|---|---|---|
| `ci.yml` | every push and PR | lint, types, tests on two Python versions, both Docker images build and answer, the model loads and the evaluation study reproduces |
| `deploy-website.yml` | push to main touching the site | runs the full suite, then deploys to Azure and waits for `/healthz` |
| `refresh-predictions.yml` | 11:30 UTC daily | the prediction job, then confirms the site recorded it |

The deploy workflow **depends on** the test job, so a failing test stops a
release rather than being discovered on the live site.

### Testing

186 tests, 82% line coverage. The ones that earn their place are the ones
guarding failures that would otherwise be silent:

- **Feature leakage.** A team's form on a match day must not include that
  day's game. This is the bug that makes a model look brilliant in testing and
  fall apart live.
- **Elo is zero-sum.** Every game moves one rating up and the other down by
  the same amount, so the league total cannot drift.
- **The model still lines up with its inputs.** The shipped model is loaded,
  handed a real feature row, and checked that the strongest club at home beats
  the weakest. A column order that had drifted out of step with training would
  pass every other test and fail this one.
- **All 127 features are present.** Asserted exactly — see the next section.
- **A transient upstream outage does not take the job down.**

---

## 8. Two bugs worth describing

### A feature that was silently missing

The model expects 127 inputs. One of them, `season_points_pct_diff`, was never
being calculated.

The pipeline builds most differences by taking the plain feature name and
subtracting away from home. But the season-record columns keep a `_before_game`
suffix on each side and drop it in the middle:
`home_season_points_pct_before_game` minus its away twin becomes
`season_points_pct_diff`. The serving code only tried the first spelling.

Nothing failed. The logistic model's imputer filled the gap with the training
average, so every prediction the site had ever made used the league-average
gap between two clubs' season records instead of the real one. It was found by
asserting exact feature coverage in a test rather than by anything going wrong.

The fix tries both spellings. There is now a test that fails if any of the 127
columns goes missing again.

### An outage that was not an outage

On 20 August 2026 the nightly job failed. The predictions had already been
calculated. What broke was a call for the club season statistics that fill the
comparison bars on the matchup page — the NHL's stats endpoint returned 503 for
about a minute, the four retries were spaced 1.5 seconds apart linearly, and
the exception took the whole job with it.

A cosmetic endpoint cost a day of predictions. Two changes:

1. **Proper backoff.** The delay now doubles and carries a random fraction, so
   a struggling server gets room to recover and every client that failed
   together does not retry together. `Retry-After` is honoured when the server
   sends it, and non-retryable codes fail immediately instead of five times.
2. **Optional data is treated as optional.** Calls the job can manage without
   go through `get_json_optional`, which warns and returns nothing. If the
   standings cannot be fetched, the job sends its predictions anyway and the
   site keeps the table it already has.

---

## 9. Security

| Concern | What is done |
|---|---|
| Passwords | Hashed with Werkzeug's PBKDF2. Never stored or logged as typed. |
| Session cookies | `HttpOnly`, `SameSite=Lax`, and `Secure` once deployed. |
| Cross-site request forgery | Every form carries a per-session token, compared with `compare_digest`. |
| SQL injection | Parameterised queries everywhere; no string interpolation of user input. |
| Cross-site scripting | Jinja2 autoescaping. A comment containing `<script>` comes back as text — tested. |
| Brute force | Sign-in is capped at 6 attempts a minute per address; the refresh endpoint at 10 an hour. |
| Response headers | CSP locking scripts to our own origin, `nosniff`, `frame-ancestors 'none'`, a referrer policy, and HSTS once on https. |
| Secrets | Read from the environment. `.secrets/` is gitignored and nothing sensitive is in the repository. |
| Account enumeration | A wrong password and an unknown username give the identical message. |
| Reverse proxy | Azure's load balancer means `remote_addr` is the balancer; the real address comes from `X-Forwarded-For`. |

The rate limiter is in-process, so with two gunicorn workers the real ceiling
is roughly double what is configured. That is a documented limitation rather
than an accident — the alternative is Redis, which is not free, and stopping
somebody grinding through a password list does not need to be exact.

---

## 10. Running it

```bash
# the website, in a container, with nothing else installed
docker compose up --build         # http://localhost:8000

# the prediction job against that container
docker compose run --rm refresh
```

```bash
# or directly
cd web
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                     # http://127.0.0.1:5000
```

```bash
# the checks CI runs
pip install -r requirements-dev.txt
ruff check .
mypy web model
pytest --cov
```

Sign in as `demo` / `puck1234`, or register.

---

## 11. Things that would be done differently

- **PostgreSQL instead of SQLite.** SQLite is right for one small worker and
  wrong for anything that needs to scale horizontally. The moment there is
  more than one machine, it has to go.
- **Redis for rate limiting**, so the limit is shared across workers.
- **Feature-level drift, not just prediction drift.** Comparing today's input
  distributions against the training distributions would catch problems
  earlier, but it needs the full dataset alongside the site.
- **Automatic retraining** when drift crosses the threshold, rather than when
  somebody looks at the page.
- **A model registry.** The bundle is a joblib file with no version stamped
  into it. Recording the training date, the git commit and the metrics inside
  the artefact would make it possible to say exactly which model produced a
  given prediction.
