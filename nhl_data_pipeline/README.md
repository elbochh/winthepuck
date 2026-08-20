# NHL Data Ingestion Pipeline

Python 3.11+ pipeline for collecting NHL prediction data from the free public NHL APIs:

- Web API: `https://api-web.nhle.com/v1`
- Stats API: `https://api.nhle.com/stats/rest/en`

The pipeline caches raw JSON responses, writes processed CSV datasets, avoids re-downloading cached files unless `--force-refresh` is used, and can resume after a crash by continuing from cached raw files.

## Setup

```bash
cd nhl_data_pipeline
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py --mode historical
python main.py --mode upcoming --days-ahead 14
python main.py --mode live
python main.py --mode build-features
python main.py --mode build-live-features --start-season 20252026 --end-season 20252026
python main.py --mode build-merged
python main.py --mode all
```

Use `--force-refresh` to re-download files that already exist.

By default, historical and all-mode runs start at `20102011`, the earliest
season verified against the current pipeline's full feature set: season
schedules, Gamecenter boxscores, play-by-play, shift charts, and team/skater/
goalie season stats. Older NHL seasons exist in the public season index, but
they have sparser event or optional-enrichment coverage, so use an explicit
`--start-season` only when you intentionally want that reduced historical
surface.

For a quick live win-probability smoke test without rebuilding every historical event row:

```bash
python main.py --mode build-live-features --start-season 20252026 --end-season 20252026 --max-games 25
```

## Outputs

Raw API responses are saved under `data/raw/`.

Processed CSVs are saved under `data/processed/`, including:

- `games.csv`
- `team_game_stats.csv`
- `player_game_stats.csv`
- `goalie_game_stats.csv`
- `play_by_play.csv`
- `upcoming_games.csv`
- `live_games.csv`
- `live_current_features.csv`
- `model_features.csv`
- `live_win_probability_features.csv`
- `merged_model_data.csv`
- `standings.csv`
- `rosters.csv`
- `team_season_stats.csv`
- `skater_season_stats.csv`
- `goalie_season_stats.csv`
- `shift_charts.csv`
- `gamecenter_matchups.csv`

## Example Preview

```bash
python - <<'PY'
import pandas as pd

for name in ["games", "team_game_stats", "player_game_stats", "model_features"]:
    path = f"data/processed/{name}.csv"
    print(f"\n{name}")
    print(pd.read_csv(path).head())
PY
```

## Feature Leakage

`model_features.csv` is built only from completed regular season games. Rolling values use games with dates strictly before the current game date, so same-day and future games are excluded from feature inputs.

`merged_model_data.csv` is a one-row-per-game modeling table for completed regular-season and playoff games. Its prediction target is `target_home_win`: `1` means the home team won, `0` means the away team won. Do not train on `home_score`, `away_score`, or `winner_team`; those are outcome/reference columns.

The merged table includes pre-game rolling features for recent team form, rest/fatigue windows, home/road splits, head-to-head history, playoff series state, goalie recent form from prior starts, even-strength shot attempt share, special-team proxy stats, and skater production aggregates. Confirmed future starting goalies, injuries, betting odds, and external expected-goals data are not included unless you add another source.

`live_win_probability_features.csv` is the in-game modeling table. It creates one row after each play-by-play event from completed games and attaches `target_home_win` plus final scores for supervised training. Its input columns are live-state features available at that event: clock, period, game progress, score, shots, shot attempts, hits, faceoffs, giveaways, takeaways, penalties, active penalty clocks, manpower/situation code, power-play opportunities/goals, short-handed goals, goalie IDs, live goalie saves/goals-against/save percentage, event location, shot type, penalty type, and player IDs involved in the current event.

For live inference, `python main.py --mode live` writes timestamped raw JSON under `data/raw/live/YYYY-MM-DD/<snapshot>/` and writes the latest available game-state row per live/upcoming game to `live_current_features.csv`. These rows intentionally leave `target_home_win` blank unless the game is already final.

The current `home_season_points_pct_before_game` and `away_season_points_pct_before_game` values use win-derived points from available game scores. If you need exact loser points for overtime or shootout losses, extend `games.csv` with `gameOutcome.lastPeriodType` from the raw schedule or landing files.

## NHL API Notes

Some boxscore-style team metrics are not exposed as a single clean team table in the Web API. The pipeline derives conservative team-game rows from game scores, player stats, and available event data. Metrics that cannot be derived safely are left blank instead of being fabricated.

Optional sources such as shift charts and Gamecenter right-rail matchup data are best-effort. Missing optional files are logged and do not stop the pipeline.

The live fetcher uses only free public NHL endpoints: `score/now`, dated `score/YYYY-MM-DD`, dated `schedule/YYYY-MM-DD`, `scoreboard/now`, and Gamecenter `landing`, `boxscore`, `play-by-play`, and `right-rail`. It follows the current `score/now` redirect to the NHL's focused score date and keeps each run as a raw immutable snapshot.

## Quality Checks

Each run prints:

- games fetched per season, for historical runs
- missing boxscore count
- missing play-by-play count
- upcoming game count
- duplicate `game_id` count in `games.csv`
- model feature leakage validation result

Logs are written to `logs/pipeline.log`.

## TODO: MoneyPuck

MoneyPuck can be added later as a separate optional enrichment layer for expected goals, goalie-adjusted metrics, and richer team/player features. It is intentionally not implemented here so the current project uses only free NHL public API data.
