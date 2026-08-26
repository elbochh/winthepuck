"""Export real data for the WinThePuck website.

Reads pipeline CSVs + model outputs, writes JSON into
frontend/data/. Every number on the site comes from here.

Outputs:
  teams.json            per-team: record, points%, streak, season stats, last-5 form
  season.json           last completed season: every walk-forward prediction vs result,
                        monthly accuracy, confidence buckets, summary metrics
  model_leaderboard.json  real model comparison from the 4-season walk-forward
  upcoming.json         games not yet played in the dataset (with predictions),
                        or [] in the offseason
  hero.json             headline stats (all real)
  live_demo.json        a real game replayed through the live model (event timeline)
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent / "pipeline" / "data" / "processed"
SITE = HERE.parent / "frontend" / "data"
SEASON = 20252026  # last completed season shown on the site

TEAM_COLORS = {
    "ANA": "#F47A38", "ARI": "#8C2633", "BOS": "#FFB81C", "BUF": "#003087",
    "CGY": "#D2001C", "CAR": "#CE1126", "CHI": "#CF0A2C", "COL": "#6F263D",
    "CBJ": "#002654", "DAL": "#006847", "DET": "#CE1126", "EDM": "#FF4C00",
    "FLA": "#C8102E", "LAK": "#111111", "MIN": "#154734", "MTL": "#AF1E2D",
    "NSH": "#FFB81C", "NJD": "#CE1126", "NYI": "#00539B", "NYR": "#0038A8",
    "OTT": "#DA1A32", "PHI": "#F74902", "PIT": "#FCB514", "SEA": "#99D9D9",
    "SJS": "#006D75", "STL": "#002F87", "TBL": "#002868", "TOR": "#00205B",
    "UTA": "#71AFE5", "VAN": "#00843D", "VGK": "#B4975A", "WPG": "#041E42",
    "WSH": "#C8102E",
}
FALLBACK_COLOR = "#64748b"


def fair_odds(p: float) -> int:
    """American odds implied by the model probability (no vig)."""
    p = min(max(p, 0.01), 0.99)
    return int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))


def team_directory() -> dict[str, dict]:
    teams = pd.read_csv(PIPE / "teams.csv")
    out = {}
    for t in teams.itertuples(index=False):
        abbr = t.triCode
        full = str(t.fullName)
        name = full.split()[-1] if abbr != "UTA" else "Hockey Club"
        city = full[: len(full) - len(name)].strip()
        out[abbr] = {"abbr": abbr, "name": name, "city": city,
                     "color": TEAM_COLORS.get(abbr, FALLBACK_COLOR)}
    return out


def latest_standings(season: int) -> pd.DataFrame:
    st = pd.read_csv(PIPE / "standings.csv")
    st = st[st["season"] == season]
    return st[st["snapshot_date"] == st["snapshot_date"].max()].copy()


def team_season_stats(season: int) -> dict[str, dict]:
    tg = pd.read_csv(PIPE / "team_game_stats.csv")
    tg = tg[(tg["season"] == season) & (tg["game_id"].astype(str).str[4:6] == "02")]
    opp = tg.rename(columns={
        "team": "opponent", "opponent": "team",
        "powerplay_goals": "opp_pp_goals",
        "powerplay_opportunities": "opp_pp_opps",
    })[["game_id", "team", "opp_pp_goals", "opp_pp_opps"]]
    tg = tg.merge(opp, on=["game_id", "team"], how="left")
    stats = {}
    for team, g in tg.groupby("team"):
        pp_opps, pp_goals = g["powerplay_opportunities"].sum(), g["powerplay_goals"].sum()
        opp_opps, opp_goals = g["opp_pp_opps"].sum(), g["opp_pp_goals"].sum()
        stats[team] = {
            "goalsFor": round(g["goals_for"].mean(), 2),
            "goalsAgainst": round(g["goals_against"].mean(), 2),
            "powerPlay": round(100 * pp_goals / pp_opps, 1) if pp_opps else None,
            "penaltyKill": round(100 * (1 - opp_goals / opp_opps), 1) if opp_opps else None,
            "shotsPerGame": round(g["shots_for"].mean(), 1),
            "faceoffWin": round(g["faceoff_win_pct"].mean(), 1),
        }
    return stats


def last5_form(games: pd.DataFrame, team: str) -> list[str]:
    g = games[((games["home_team"] == team) | (games["away_team"] == team))
              & games["home_win"].notna()].sort_values("game_date").tail(5)
    form = []
    for row in g.itertuples(index=False):
        is_home = row.home_team == team
        won = bool(row.home_win) == is_home
        # OT/SO losses aren't split out in games.csv scores; mark plain W/L
        form.append("W" if won else "L")
    return form


def export_teams(games: pd.DataFrame) -> dict[str, dict]:
    directory = team_directory()
    st = latest_standings(SEASON)
    stats = team_season_stats(SEASON)
    teams = {}
    for row in st.itertuples(index=False):
        abbr = row.team
        base = directory.get(abbr) or {"abbr": abbr, "name": abbr, "city": "",
                                       "color": FALLBACK_COLOR}
        teams[abbr] = {
            **base,
            "record": f"{int(row.wins)}-{int(row.losses)}-{int(row.otLosses)}",
            "points": int(row.points),
            "pointsPct": round(float(row.pointPctg), 3),
            "streak": f"{row.streakCode}{int(row.streakCount)}",
            "gamesPlayed": int(row.gamesPlayed),
            "stats": stats.get(abbr, {}),
            "form": last5_form(games, abbr),
        }
    (SITE / "teams.json").write_text(json.dumps(teams, indent=1))
    print(f"teams.json: {len(teams)} teams")
    return teams


def export_season(games: pd.DataFrame) -> dict:
    wf = pd.read_csv(HERE / "data" / "walkforward_predictions.csv",
                     parse_dates=["game_date"])
    season = wf[wf["season"] == SEASON].copy()
    g = games[["game_id", "home_team", "away_team", "home_score", "away_score",
               "game_type"]].copy()
    season = season.merge(g, on="game_id", how="left", suffixes=("", "_g"))
    season["pick_home"] = season["p_home"] >= 0.5
    season["correct"] = season["pick_home"].astype(int) == season["y"]
    season = season.sort_values("game_date")

    rows = [
        {
            "id": int(r.game_id),
            "date": r.game_date.strftime("%Y-%m-%d"),
            "home": r.home_team, "away": r.away_team,
            "homeScore": int(r.home_score), "awayScore": int(r.away_score),
            "pHome": round(float(r.p_home), 3),
            "pick": r.home_team if r.pick_home else r.away_team,
            "winner": r.home_team if r.y == 1 else r.away_team,
            "correct": bool(r.correct),
            "playoff": int(r.game_type) == 3,
        }
        for r in season.itertuples(index=False)
    ]

    monthly = [
        {"month": str(m), "n": int(len(g)), "accuracy": round(g["correct"].mean(), 4)}
        for m, g in season.groupby(season["game_date"].dt.strftime("%Y-%m"))
    ]

    conf = np.maximum(season["p_home"], 1 - season["p_home"])
    buckets = []
    for lo, hi in [(0.5, 0.55), (0.55, 0.6), (0.6, 0.65), (0.65, 0.7), (0.7, 1.01)]:
        sel = season[(conf >= lo) & (conf < hi)]
        if len(sel):
            buckets.append({"range": f"{int(lo*100)}–{int(min(hi,1)*100)}%",
                            "n": int(len(sel)),
                            "accuracy": round(sel["correct"].mean(), 4)})

    payload = {
        "season": "2025–26",
        "summary": {
            "games": int(len(season)),
            "accuracy": round(season["correct"].mean(), 4),
            "highConfidenceAccuracy": round(season[conf >= 0.60]["correct"].mean(), 4),
            "highConfidenceGames": int((conf >= 0.60).sum()),
            "logLoss": round(float(-(season["y"] * np.log(season["p_home"].clip(1e-9))
                             + (1 - season["y"]) * np.log((1 - season["p_home"]).clip(1e-9))).mean()), 4),
        },
        "monthly": monthly,
        "confidenceBuckets": buckets,
        "games": rows,
    }
    (SITE / "season.json").write_text(json.dumps(payload, indent=1))
    print(f"season.json: {len(rows)} games, accuracy {payload['summary']['accuracy']:.1%}")
    return payload


def export_model_leaderboard() -> None:
    wf = pd.read_csv(HERE / "data" / "walkforward_predictions.csv")
    models = {
        "WinThePuck Ensemble": "p_home",
        "Logistic Regression": "p_logit",
        "Gradient Boosting": "p_hgb",
        "CatBoost": "p_catboost",
        "Elo Baseline": "elo_prob_home",
    }
    rows = []
    for name, col in models.items():
        if col not in wf.columns:
            continue
        correct = ((wf[col] >= 0.5).astype(int) == wf["y"])
        ll = -(wf["y"] * np.log(wf[col].clip(1e-9))
               + (1 - wf["y"]) * np.log((1 - wf[col]).clip(1e-9))).mean()
        # longest streak of consecutive correct picks (chronological)
        c = correct.to_numpy()
        streak = max_streak = 0
        for v in c:
            streak = streak + 1 if v else 0
            max_streak = max(max_streak, streak)
        rows.append({
            "model": name,
            "accuracy": round(100 * correct.mean(), 1),
            "logLoss": round(float(ll), 4),
            "correctPicks": int(correct.sum()),
            "games": int(len(wf)),
            "bestStreak": int(max_streak),
        })
    rows.sort(key=lambda r: -r["accuracy"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    (SITE / "model_leaderboard.json").write_text(json.dumps(rows, indent=1))
    print(f"model_leaderboard.json: {len(rows)} models over {rows[0]['games']} games")


def export_upcoming(games: pd.DataFrame, teams: dict) -> None:
    """Games still unplayed in the dataset, with model predictions."""
    up_path = HERE / "data" / "upcoming_predictions.csv"
    fut = games[games["home_win"].isna() & (games["game_state"] == "FUT")]
    payload = []
    if up_path.exists() and len(fut):
        preds = pd.read_csv(up_path)
        preds = preds.merge(
            fut[["game_id", "game_date", "start_time_utc", "home_team", "away_team"]],
            on=["home_team", "away_team"], how="inner")
        preds = preds.drop_duplicates("game_id").sort_values("start_time_utc")
        for r in preds.itertuples(index=False):
            p = float(r.p_home_win)
            payload.append({
                "id": int(r.game_id),
                "startsAt": r.start_time_utc,
                "home": r.home_team, "away": r.away_team,
                "pHome": round(p, 3),
                "confidence": round(max(p, 1 - p), 3),
                "homeOdds": fair_odds(p),
                "awayOdds": fair_odds(1 - p),
                "pick": r.home_team if p >= 0.5 else r.away_team,
            })
    (SITE / "upcoming.json").write_text(json.dumps(payload, indent=1))
    print(f"upcoming.json: {len(payload)} games")


def export_hero(season_payload: dict) -> None:
    live = pd.read_csv(PIPE / "live_win_probability_features.csv",
                       usecols=["game_id"])
    events_per_game = live.groupby("game_id").size()
    wf = pd.read_csv(HERE / "data" / "walkforward_predictions.csv")
    conf = np.maximum(wf["p_home"], 1 - wf["p_home"])
    hc = wf[conf >= 0.60]
    hc_acc = ((hc["p_home"] >= 0.5).astype(int) == hc["y"]).mean()
    md = pd.read_csv(HERE / "data" / "model_dataset.csv", usecols=["game_id"])
    payload = {
        "confidentAccuracy": round(100 * hc_acc, 1),
        "confidentGames": int(len(hc)),
        "gamesTracked": int(len(md)),
        "predictedGames": int(len(wf)),
        "liveUpdatesPerGame": int(events_per_game.median()),
        "seasonAccuracy": round(100 * season_payload["summary"]["accuracy"], 1),
    }
    (SITE / "hero.json").write_text(json.dumps(payload, indent=1))
    print(f"hero.json: {payload}")


def export_live_demo(games: pd.DataFrame) -> None:
    """Replay the most exciting recent playoff game through the live model."""
    bundle = joblib.load(HERE / "models" / "live_model.joblib")
    model, iso, feats = bundle["model"], bundle["iso"], bundle["features"]

    wf = pd.read_csv(HERE / "data" / "walkforward_predictions.csv",
                     usecols=["game_id", "p_home"])
    live_ids = set(pd.read_csv(PIPE / "live_win_probability_features.csv",
                               usecols=["game_id"])["game_id"].unique())
    # latest playoff game with live event coverage and a close final score
    completed = games[games["home_win"].notna()].copy()
    completed = completed[completed["game_id"].isin(live_ids)]
    playoffs = completed[completed["game_type"] == 3].sort_values("game_date")
    candidates = playoffs[abs(playoffs["home_score"] - playoffs["away_score"]) <= 1]
    game = (candidates if len(candidates) else playoffs).iloc[-1]
    gid = int(game.game_id)

    live = pd.read_csv(PIPE / "live_win_probability_features.csv")
    ev = live[live["game_id"] == gid].sort_values("event_index").copy()
    prior = wf.loc[wf["game_id"] == gid, "p_home"]
    ev["pregame_home_prob"] = float(prior.iloc[0]) if len(prior) else 0.54
    ev["score_diff_per_sqrt_time"] = ev["score_diff_home"] / np.sqrt(
        ev["seconds_remaining_regulation"].clip(lower=0) + 1.0)
    ev["is_playoff"] = (ev["game_type"] == 3).astype(int)
    p = iso.predict(model.predict_proba(ev[feats].to_numpy(dtype=float))[:, 1])
    ev["p_home"] = p

    # keep the moments people care about + a steady pulse
    key = ev["event_type"].isin(["goal", "penalty", "period-start", "period-end"])
    pulse = ev["event_index"] % max(1, len(ev) // 30) == 0
    keep = ev[key | pulse].copy()

    def label(r) -> str:
        team = r.event_team if isinstance(r.event_team, str) else ""
        names = {"goal": f"{team} goal", "penalty": f"{team} penalty",
                 "period-start": f"Period {int(r.period)} starts",
                 "period-end": f"End of period {int(r.period)}",
                 "faceoff": "Faceoff", "shot-on-goal": f"{team} shot on goal",
                 "blocked-shot": "Shot blocked", "missed-shot": f"{team} shot misses",
                 "hit": f"{team} hit", "giveaway": f"{team} giveaway",
                 "takeaway": f"{team} takeaway", "stoppage": "Play stopped",
                 "game-end": "Final horn"}
        return names.get(r.event_type, str(r.event_type).replace("-", " ").capitalize())

    timeline = [
        {
            "minute": round(float(r.seconds_elapsed) / 60, 1),
            "period": int(r.period),
            "clock": str(r.time_remaining),
            "label": label(r),
            "team": (r.event_team_side if isinstance(r.event_team_side, str) else "neutral"),
            "homeProb": round(100 * float(r.p_home), 1),
            "homeScore": int(r.home_score), "awayScore": int(r.away_score),
        }
        for r in keep.itertuples(index=False)
    ]
    payload = {
        "gameId": gid,
        "date": str(game.game_date)[:10],
        "label": "Playoff replay",
        "home": game.home_team, "away": game.away_team,
        "finalHome": int(game.home_score), "finalAway": int(game.away_score),
        "pregameHomeProb": round(100 * float(ev["pregame_home_prob"].iloc[0]), 1),
        "timeline": timeline,
    }
    (SITE / "live_demo.json").write_text(json.dumps(payload, indent=1))
    print(f"live_demo.json: game {gid} {game.away_team}@{game.home_team} "
          f"{int(game.away_score)}-{int(game.home_score)}, {len(timeline)} events")


def main() -> None:
    SITE.mkdir(exist_ok=True)
    games = pd.read_csv(PIPE / "games.csv", parse_dates=["game_date"])
    games = games[games["season"] == SEASON]
    teams = export_teams(games)
    season_payload = export_season(games)
    export_model_leaderboard()
    export_upcoming(games, teams)
    export_hero(season_payload)
    export_live_demo(games)
    print("done")


if __name__ == "__main__":
    main()
