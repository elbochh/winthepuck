# Model card — WinThePuck pre-game win probability

A short, honest description of what this model is, how well it works, where it
stops working, and what it should not be used for. The layout follows the
model card format proposed by Mitchell et al. (2019), which is the usual way
to write this down.

**Live:** <https://winthepuck.azurewebsites.net> ·
**Health of the deployed model:** <https://winthepuck.azurewebsites.net/monitoring>

---

## 1. Model details

| | |
|---|---|
| **Task** | Binary classification — will the home team win? |
| **Output** | A probability between 0 and 1, shown as a percentage |
| **Type** | Soft-voting ensemble of three classifiers, averaged with equal weights |
| **Components** | `HistGradientBoostingClassifier`, `LogisticRegression` (median imputer → standard scaler → L2), `CatBoostClassifier` (600 iterations, depth 4) |
| **Inputs** | 127 numeric features per game |
| **Trained on** | 20,591 completed NHL games |
| **Trained up to** | 14 June 2026 |
| **Artefact** | `serving/pregame_model.joblib` (~1.8 MB) |
| **Frameworks** | scikit-learn 1.7.2, CatBoost 1.2.10, NumPy 2.3.5 |
| **Licence / cost** | Student coursework. Every data source is free and needs no API key. |

### What goes into it

The 127 features fall into five groups:

1. **Elo rating** — a FiveThirtyEight-style implementation: K = 6, home ice
   worth 50 rating points, a margin-of-victory multiplier so a 5–1 win counts
   for more than a 2–1 win, and a 30% reversion towards the league average
   every summer.
2. **Recent form** — last 5 and last 10 win rate, goals for and against,
   goal difference, exponentially-decayed form.
3. **Schedule and fatigue** — days of rest, back-to-back games, games played
   in the last 3, 7 and 14 days.
4. **Season splits** — points percentage, and separate home and road records.
5. **Box-score rolling averages** — shots, shot attempts, hits, blocked shots,
   faceoffs, penalty minutes, and the starting goalie's recent save
   percentage.

About half the inputs appear twice: once per team, and once as a home-minus-away
difference.

---

## 2. Intended use

**Intended:** a coursework demonstration of an end-to-end machine learning
system — data collection, feature engineering, honest evaluation, deployment
and monitoring. The website exists so the predictions can be inspected and
argued with.

**Not intended:**

- **Betting.** The odds shown on the site are the *fair* odds implied by the
  model with no bookmaker margin added. They are a restatement of the
  probability, not a recommendation. The model does not beat the closing line
  and is not built to.
- **Anything about individual players.** It predicts one thing: which club
  wins.
- **Live in-game prediction.** Everything is pre-game. The win-probability
  replay on the home page is a recording of one finished playoff game, not a
  live model.

---

## 3. How it was evaluated

Walk-forward, which is the only fair way to test a model that predicts the
future. To predict the games in a given month, the model is retrained on
games that finished before that month started, and never sees a result from
the month it is being asked about.

- **5,592 games** across **four seasons** (2022-23 to 2025-26)
- Every probability quoted below was produced before the game was played

Splitting the data at random instead would have let the model learn from
March to predict January, and would have made it look far better than it is.

---

## 4. How well it works

### Overall, across all 5,592 games

| Metric | Value | What it means |
|---|---|---|
| Accuracy | **58.6%** | How often the favourite it picked won |
| Log loss | **0.6662** | Below 0.6931, the score for saying "50%" every time |
| Brier score | **0.2370** | Mean squared error of the probabilities |
| Calibration error (ECE) | **1.31 points** | Stated confidence is out by about 1.3 points on average |

For context: published research puts the ceiling for single-game NHL
prediction near 62%, and bookmakers' closing lines land around 59–60%. A third
of NHL games are decided by one bounce, and that is not a modelling problem —
it is the sport.

### It knows when it knows

On the 2,356 games it was at least 60% sure about, it was right **65.4%** of
the time. That is what makes the confidence figure worth showing.

| Model said | Games | It really happened |
|---|---|---|
| 50–55% | 1,742 | 51.3% |
| 55–60% | 1,494 | 56.4% |
| 60–65% | 1,220 | 60.6% |
| 65–70% | 664 | 66.6% |
| 70–75% | 331 | 73.7% |
| 75–80% | 128 | 82.8% |

The two columns track each other closely, which is the point: the model's
confidence means what it says.

### Against the alternatives

| Model | Accuracy | Log loss |
|---|---|---|
| **Ensemble (deployed)** | **58.6%** | **0.6662** |
| Logistic regression alone | 58.6% | 0.6665 |
| CatBoost alone | 58.4% | 0.6680 |
| Gradient boosting alone | 58.2% | 0.6687 |
| Elo rating alone | 57.6% | 0.6726 |

The ensemble wins, but narrowly. Most of the signal is in the Elo rating; the
other 120-odd features are worth about one accuracy point between them.

---

## 5. Where it gets worse

### It is ageing

| Season | Games | Accuracy | Log loss | Spread of predictions |
|---|---|---|---|---|
| 2022-23 | 1,400 | 59.6% | 0.6628 | 0.113 |
| 2023-24 | 1,400 | 61.1% | 0.6555 | 0.118 |
| 2024-25 | 1,398 | 58.3% | 0.6610 | 0.106 |
| 2025-26 | 1,394 | **55.4%** | **0.6857** | **0.092** |

Two things are happening together, and they are the most important finding in
this card. Accuracy is falling, and the model is hedging — the spread of its
probabilities is narrowing towards 50%. Calibration error over the same period
went from 1.02 to 3.29 points.

This is what a model drifting away from its training distribution looks like.
It is the reason the deployed site has a `/monitoring` page rather than just a
published accuracy figure.

### Home ice keeps moving

The model implicitly assumes home teams win about 54.4% of the time. The real
figure over these four seasons was 52.0%, 53.7%, 56.5% and 51.9%. A fixed
assumption is meeting a moving target.

### Other known weak spots

- **Playoffs** — 55.8% across 344 playoff games, against 58.8% in the regular
  season. Short series, tighter checking, and goalies who get hot.
- **The first few weeks of a season** — with no current-season form to work
  with, the model falls back on last season's ratings and hedges towards 50%.
- **Anything the box score cannot see** — injuries, a goalie announced an hour
  before the game, trades, travel, a team resting players once its playoff
  place is settled. None of it is an input.

---

## 6. Three fixes that were tried and rejected

The falling accuracy and rising calibration error look like a model that has
become over-confident, and there are standard corrections for that. Three were
tested properly: each was tuned on the first three seasons and then applied
**once** to the fourth, which was not looked at until the final table.

| Candidate | Log loss change on the held-out season | Kept? |
|---|---|---|
| Platt scaling | +0.0005 | No |
| Adaptive home-ice advantage | −0.0003 | No |
| Fitted ensemble weights | −0.0004 | No |
| Fitted ensemble weights + Elo | −0.0002 | No |

Every one of them gained roughly 0.0004 log loss on the seasons it was tuned
on, and none of that survived contact with the held-out season. On 1,394
games, differences that size are noise. Shipping one would have added
complexity and a second thing to maintain in exchange for nothing.

Two things follow from that:

- **The equal-weight ensemble stays.** It is the simplest option and nothing
  measurably beats it.
- **The problem is not calibration, it is age.** Post-hoc corrections cannot
  fix a model that has drifted; only retraining can. So the effort went into
  detecting drift instead of papering over it.

The experiment is reproducible in about thirty seconds:

```bash
cd "model"
python3 evaluate_model.py
```

It writes `serving/evaluation_report.json`, and CI fails if the numbers in
this card and the numbers in that file stop agreeing.

---

## 7. Monitoring in production

`/monitoring` on the live site recomputes, from the database, three things the
published accuracy figure cannot tell you:

- **Calibration** — the reliability table above, rebuilt from real results.
- **Prediction drift** — the population stability index between the spread of
  today's predictions and the spread during testing. Under 0.10 is normal;
  over 0.25 means the model is due a retrain. Readings taken from a short
  slate of games are labelled provisional, because a quiet week can move PSI
  on its own.
- **Live accuracy** — games this deployment predicted itself and which have
  since been played, compared against the walk-forward baseline. Nothing is
  shown until at least 30 games have been settled, because below that any
  figure is mostly noise.

---

## 8. Ethical and practical considerations

- **It is not betting advice**, and the site says so on every page. Fair odds
  with no margin are shown precisely so they cannot be mistaken for an edge.
- **No personal data.** The model uses club-level statistics only. Site
  accounts store a username and a hashed password, nothing more.
- **The data is public.** Everything comes from the NHL's own free API. Team
  crests are served from the NHL's asset host and remain the property of the
  NHL and its clubs.
- **The published numbers are the honest ones.** Accuracy is quoted from
  walk-forward testing, not from a training score, and the misses are on the
  results page next to the hits.

---

## 9. What would be done next

1. **Retrain on the completed 2025-26 season.** The evidence above says this
   is the single most valuable change available.
2. **Feed goalie confirmations in.** The starting goalie is usually announced
   an hour before the game and is probably the largest piece of information
   the model currently ignores.
3. **Retrain automatically when drift crosses the threshold**, rather than
   when somebody notices.
4. **Track feature-level drift, not just prediction drift.** That needs the
   full 18 GB dataset in the cloud, which does not fit the free tier today.

---

*Last updated 25 August 2026. Model trained to 14 June 2026.*
