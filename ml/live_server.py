"""Live win-probability WebSocket server.

Broadcasts JSON snapshots on ws://localhost:8765 for the website's live section.

Modes (auto-selected each cycle):
  LIVE    — if the NHL is playing right now: refresh the data pipeline's live
            snapshot (`main.py --mode live`), run the current game state through
            the pregame prior + live model, broadcast one snapshot per game.
  REPLAY  — otherwise (offseason / no games): replay a real recent playoff game
            through the live model at ~40x speed so the UI always has a live feed.

Message shape:
  {"type": "snapshot", "mode": "replay"|"live", "gameId", "home", "away",
   "period", "clock", "homeScore", "awayScore", "homeProb", "label",
   "team": "home"|"away"|"neutral", "minute", "final": bool}

Run: python3 live_server.py [--port 8765] [--replay-game GAME_ID] [--speed 40]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import websockets

HERE = Path(__file__).resolve().parent
PIPELINE = HERE.parent / "pipeline"
PROCESSED = PIPELINE / "data" / "processed"

CLIENTS: set = set()


def load_bundle():
    b = joblib.load(HERE / "models" / "live_model.joblib")
    return b["model"], b["iso"], b["features"]


def predict_events(ev: pd.DataFrame, model, iso, feats, pregame_prob: float) -> np.ndarray:
    ev = ev.copy()
    ev["pregame_home_prob"] = pregame_prob
    ev["score_diff_per_sqrt_time"] = ev["score_diff_home"] / np.sqrt(
        ev["seconds_remaining_regulation"].clip(lower=0) + 1.0)
    if "is_playoff" not in ev:
        ev["is_playoff"] = (ev["game_type"] == 3).astype(int)
    X = ev.reindex(columns=feats).to_numpy(dtype=float)
    return iso.predict(model.predict_proba(X)[:, 1])


def event_label(r) -> str:
    team = r.event_team if isinstance(getattr(r, "event_team", None), str) else ""
    names = {"goal": f"{team} GOAL", "penalty": f"{team} penalty",
             "period-start": f"Period {int(r.period)} starts",
             "period-end": f"End of period {int(r.period)}",
             "shot-on-goal": f"{team} shot on goal", "faceoff": "Faceoff won",
             "blocked-shot": "Shot blocked", "missed-shot": f"{team} shot misses",
             "hit": f"{team} big hit", "giveaway": f"{team} giveaway",
             "takeaway": f"{team} takeaway", "stoppage": "Play stopped",
             "game-end": "Final horn"}
    return names.get(r.event_type, str(r.event_type).replace("-", " ").capitalize())


async def broadcast(msg: dict) -> None:
    if not CLIENTS:
        return
    dead = []
    data = json.dumps(msg)
    for ws in CLIENTS:
        try:
            await ws.send(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        CLIENTS.discard(ws)


def pick_replay_game(replay_game: int | None) -> int:
    if replay_game:
        return replay_game
    live_ids = set(pd.read_csv(PROCESSED / "live_win_probability_features.csv",
                               usecols=["game_id"])["game_id"].unique())
    games = pd.read_csv(PROCESSED / "games.csv")
    done = games[games["home_win"].notna() & games["game_id"].isin(live_ids)]
    playoffs = done[done["game_type"] == 3].sort_values("game_date")
    close = playoffs[abs(playoffs["home_score"] - playoffs["away_score"]) <= 1]
    return int((close if len(close) else playoffs).iloc[-1].game_id)


def load_replay(gid: int, model, iso, feats) -> tuple[pd.DataFrame, dict]:
    live = pd.read_csv(PROCESSED / "live_win_probability_features.csv")
    ev = live[live["game_id"] == gid].sort_values("event_index").copy()
    if ev.empty:
        raise SystemExit(f"game {gid} not in live features")
    wf_path = HERE / "data" / "walkforward_predictions.csv"
    prior = 0.54
    if wf_path.exists():
        wf = pd.read_csv(wf_path, usecols=["game_id", "p_home"])
        m = wf[wf["game_id"] == gid]
        if len(m):
            prior = float(m["p_home"].iloc[0])
    ev["p_home_live"] = predict_events(ev, model, iso, feats, prior)
    meta = {
        "gameId": gid,
        "home": ev["home_team"].iloc[0], "away": ev["away_team"].iloc[0],
        "pregameHomeProb": prior,
    }
    return ev, meta


async def replay_loop(replay_game: int | None, speed: float, model, iso, feats) -> None:
    """Stream one full pass of the replay, then return so the caller can
    re-check for real live games between passes."""
    gid = pick_replay_game(replay_game)
    ev, meta = load_replay(gid, model, iso, feats)
    print(f"replay: game {gid} {meta['away']} @ {meta['home']} ({len(ev)} events, {speed}x)")
    prev_t = 0.0
    for r in ev.itertuples(index=False):
        t = float(r.seconds_elapsed)
        await asyncio.sleep(max(0.05, min((t - prev_t) / speed, 3.0)))
        prev_t = t
        await broadcast({
            "type": "snapshot", "mode": "replay", **meta,
            "period": int(r.period), "clock": str(r.time_remaining),
            "homeScore": int(r.home_score), "awayScore": int(r.away_score),
            "homeProb": round(100 * float(r.p_home_live), 1),
            "label": event_label(r),
            "team": r.event_team_side if isinstance(r.event_team_side, str) else "neutral",
            "minute": round(t / 60, 1),
            "final": r.event_type == "game-end",
        })
    home_won = int(ev["home_score"].iloc[-1]) > int(ev["away_score"].iloc[-1])
    await broadcast({"type": "snapshot", "mode": "replay", **meta,
                     "period": int(ev["period"].iloc[-1]), "clock": "00:00",
                     "homeScore": int(ev["home_score"].iloc[-1]),
                     "awayScore": int(ev["away_score"].iloc[-1]),
                     "homeProb": 100.0 if home_won else 0.0,
                     "label": "Final", "team": "neutral",
                     "minute": round(float(ev["seconds_elapsed"].iloc[-1]) / 60, 1),
                     "final": True})
    await asyncio.sleep(6)  # brief pause before the caller re-checks live games


def refresh_live_snapshot() -> pd.DataFrame:
    """Ask the data pipeline for the current live game state (free NHL API)."""
    subprocess.run([sys.executable, "main.py", "--mode", "live"],
                   cwd=PIPELINE, capture_output=True, timeout=300)
    path = PROCESSED / "live_current_features.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    live_states = {"LIVE", "CRIT"}
    return df[df["game_state"].isin(live_states)] if "game_state" in df else df.iloc[0:0]


async def live_loop(poll_seconds: int, model, iso, feats) -> bool:
    """Poll real live games; returns False if nothing is live (caller falls back)."""
    priors: dict[int, float] = {}
    snap = await asyncio.to_thread(refresh_live_snapshot)
    if snap.empty:
        return False
    print(f"live mode: {len(snap)} game(s) in progress")
    while True:
        for r_idx, row in snap.iterrows():
            gid = int(row["game_id"])
            prior = priors.setdefault(gid, 0.54)
            ev = snap.loc[[r_idx]]
            p = predict_events(ev, model, iso, feats, prior)[0]
            await broadcast({
                "type": "snapshot", "mode": "live", "gameId": gid,
                "home": row["home_team"], "away": row["away_team"],
                "period": int(row.get("period", 1) or 1),
                "clock": str(row.get("time_remaining", "")),
                "homeScore": int(row.get("home_score", 0) or 0),
                "awayScore": int(row.get("away_score", 0) or 0),
                "homeProb": round(100 * float(p), 1),
                "label": "Live update", "team": "neutral",
                "minute": round(float(row.get("seconds_elapsed", 0) or 0) / 60, 1),
                "final": False,
            })
        await asyncio.sleep(poll_seconds)
        snap = await asyncio.to_thread(refresh_live_snapshot)
        if snap.empty:
            print("no more live games; back to replay")
            return False


async def handler(ws) -> None:
    CLIENTS.add(ws)
    try:
        await ws.wait_closed()
    finally:
        CLIENTS.discard(ws)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--replay-game", type=int, default=None)
    ap.add_argument("--speed", type=float, default=40.0)
    ap.add_argument("--poll-seconds", type=int, default=20)
    ap.add_argument("--no-live", action="store_true",
                    help="skip NHL live polling, replay only")
    args = ap.parse_args()

    model, iso, feats = load_bundle()

    async def rotate():
        while True:
            if not args.no_live:
                try:
                    went_live = await live_loop(args.poll_seconds, model, iso, feats)
                    if went_live is False:
                        pass  # fall through to replay
                except Exception as exc:
                    print(f"live polling failed ({exc}); using replay")
            try:
                await replay_loop(args.replay_game, args.speed, model, iso, feats)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"replay error: {exc}")
                await asyncio.sleep(5)

    async with websockets.serve(handler, "localhost", args.port):
        print(f"live server on ws://localhost:{args.port}")
        await rotate()


if __name__ == "__main__":
    asyncio.run(main())
