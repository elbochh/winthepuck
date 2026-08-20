# IceEdge / WinThePuck — NHL Prediction Website

Next.js 16 frontend for the WinThePuck NHL prediction project. Every number on
the site is real model output — no mock data.

## Architecture

```
nhl_data_pipeline  (Python)   free NHL APIs → CSVs (games, stats, play-by-play)
nhl_model          (Python)   pregame ensemble + in-game live model
      │  export_site_data.py  → data/*.json   (this repo)
      │  live_server.py       → ws://localhost:8765 (live win probability)
      ▼
nhl-prediction-website (this repo, Next.js 16)
      app/page.tsx            home: hero, live section, Cup Final calls,
                              matchups, model leaderboard, discussion
      app/season/page.tsx     2025–26 season review: every prediction vs result
      app/api/data/[dataset]  read-only JSON API (the future cloud surface)
      lib/server-data.ts      data access seam (fs today, Azure later)
```

## Run locally

```bash
# 1. (once, or after new games) refresh data + models + exports
cd ../nhl_model && ./refresh_all.sh

# 2. live win-probability feed (optional but recommended)
python3 ../nhl_model/live_server.py     # ws://localhost:8765

# 3. the website
npm install
npm run dev                              # http://localhost:3000
```

Without the live server the live section falls back to an in-browser replay
(`data/live_demo.json`) computed by the same in-game model.

## Live updates

`components/live-game.tsx` connects to the WebSocket. During the NHL season
the Python server polls the free NHL live API and streams the in-game model's
probability for real games; in the offseason it replays a real playoff game
event-by-event at ~40x speed. Set `NEXT_PUBLIC_LIVE_WS` to point elsewhere.

## Azure (pending — course hasn't covered cloud yet)

The only missing piece is deployment. The seams are ready:

- **Static + SSR hosting**: deploy this Next.js app to Azure App Service or
  Azure Static Web Apps.
- **Data API**: `app/api/data/[dataset]/route.ts` serves the exported JSON;
  on Azure, point it at Blob Storage (or move the JSON to Azure SQL) — the
  response shapes stay identical, so no frontend changes.
- **Live feed**: replace `ws://localhost:8765` with Azure Web PubSub and run
  `live_server.py` as an Azure Container App / Function on a timer.
- **Model refresh**: run `refresh_all.sh` as a scheduled job (Azure Container
  Apps jobs) after each game day.

## Where the numbers come from

- Hero + leaderboard: 5,575-game walk-forward test (2022–2026), models
  retrained monthly, never shown a game before predicting it.
- Season review: every 2025–26 game, predicted before puck drop.
- Team records/stats: official NHL standings + per-game data.
- Live probabilities: second-stage gradient-boosting model (AUC 0.81 on the
  held-out 2025–26 season) stacked on the pregame ensemble.
