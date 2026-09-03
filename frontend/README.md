# WinThePuck: the React front end

A second interface for the WinThePuck predictions, built with Next.js 16,
React 19 and TypeScript. Every number on it is real model output, and there is
no mock data anywhere in this folder.

The deployed site at
[winthepuck.azurewebsites.net](https://winthepuck.azurewebsites.net) is the
Flask app in [`../web`](../web). This one exists because it does something the
Flask site does not: it replays the **in-game win probability model** shift by
shift, so you can watch the line move on a goal.

## What is on it

- **Home**, showing the pre-game slate, the in-game replay, how the model called the
  Stanley Cup Final, a head-to-head comparison, and the model leaderboard.
- **Season review**, every prediction the model made last season next to what
  actually happened, misses included.

## Where the data comes from

```
pipeline/  (Python)   free NHL APIs -> CSVs (games, stats, play-by-play)
ml/        (Python)   pre-game ensemble + in-game live model
    │  export_site_data.py  -> data/*.json  (this folder)
    │  live_server.py       -> ws://localhost:8765  (live win probability)
    ▼
frontend/  (Next.js 16)
    app/page.tsx             home
    app/season/page.tsx      season review
    app/api/data/[dataset]   read-only JSON API over the exported files
    lib/server-data.ts       the data-access seam
```

`lib/server-data.ts` is deliberately a seam. Today it reads JSON from disk; the
same routes could read from Blob Storage or a database without the components
changing, because the response shapes stay the same.

## Running it

```bash
npm install
npm run dev          # http://localhost:3000
```

The exported JSON in `data/` is committed, so it runs straight away. To
regenerate it from a fresh model run:

```bash
cd ../ml && ./refresh_all.sh
```

## Checks

```bash
npx tsc --noEmit     # types
npm run build        # production build
npm run lint
```

## Honest status

This is the **secondary** interface. The Flask app is what is deployed, what
the daily job posts to, and what has the accounts, picks and monitoring. This
one reads a snapshot exported from the model rather than talking to the live
API, so its schedule data is only as fresh as the last export.

Wiring it to the live `/api/*` endpoints is the obvious next step.
