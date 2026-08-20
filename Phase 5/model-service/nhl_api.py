"""Small client for the NHL's free public API (api-web.nhle.com).

The Phase 1 data pipeline is far too big to put in the cloud (18 GB of raw
play-by-play), so for Phase 5 we only keep the few endpoints the website
actually needs at run time:

  * the schedule and the final scores of a whole season, one call per club
  * the standings table (records, points, streaks)
  * the club season stats we show on the matchup page

Everything here is free, needs no API key and no login.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
import json
from datetime import date, datetime
from typing import Any

WEB_API = "https://api-web.nhle.com/v1"
STATS_API = "https://api.nhle.com/stats/rest/en"

USER_AGENT = "WinThePuck/1.0 (student project)"
TIMEOUT = 30
RETRIES = 4


def get_json(url: str) -> dict[str, Any]:
    """Ask the NHL API for one address and give back the answer as a dict."""
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {}
            last_error = error
        except Exception as error:            # network hiccup, try again
            last_error = error
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"NHL API failed for {url}: {last_error}")


def team_abbrevs(season: int) -> list[str]:
    """The three letter codes of every club that plays in a season."""
    payload = get_json(f"{STATS_API}/team/summary?cayenneExp=seasonId={season}")
    codes = sorted({row["teamFullName"]: row for row in payload.get("data", [])})
    if codes:
        # the summary endpoint gives full names, so map them through /team
        directory = get_json(f"{STATS_API}/team")
        by_name = {t["fullName"]: t["triCode"] for t in directory.get("data", [])}
        return sorted({by_name[name] for name in codes if name in by_name})
    return []


def season_games(team: str, season: int) -> list[dict[str, Any]]:
    """Every game one club plays in a season, with the score if it is over."""
    payload = get_json(f"{WEB_API}/club-schedule-season/{team}/{season}")
    return payload.get("games", [])


def flatten_game(game: dict[str, Any]) -> dict[str, Any]:
    """Keep only the parts of a game we care about."""
    home, away = game["homeTeam"], game["awayTeam"]
    outcome = game.get("gameOutcome") or {}
    state = game.get("gameState", "FUT")
    finished = state in {"OFF", "FINAL"}
    return {
        "game_id": int(game["id"]),
        "season": int(game["season"]),
        "game_type": int(game["gameType"]),        # 1 pre, 2 regular, 3 playoff
        "game_date": game["gameDate"],
        "start_time_utc": game.get("startTimeUTC", ""),
        "venue": (game.get("venue") or {}).get("default", ""),
        "home_team": home["abbrev"],
        "away_team": away["abbrev"],
        "home_logo": home.get("logo", ""),
        "away_logo": away.get("logo", ""),
        "home_name": (home.get("commonName") or {}).get("default", ""),
        "away_name": (away.get("commonName") or {}).get("default", ""),
        "home_city": (home.get("placeName") or {}).get("default", ""),
        "away_city": (away.get("placeName") or {}).get("default", ""),
        "home_score": home.get("score") if finished else None,
        "away_score": away.get("score") if finished else None,
        "last_period_type": outcome.get("lastPeriodType", ""),   # REG / OT / SO
        "state": state,
        "finished": finished,
    }


def all_games(season: int, teams: list[str] | None = None) -> list[dict[str, Any]]:
    """Every game of a whole season (each game is only kept once)."""
    teams = teams or DEFAULT_TEAMS
    by_id: dict[int, dict[str, Any]] = {}
    for team in teams:
        for game in season_games(team, season):
            row = flatten_game(game)
            by_id[row["game_id"]] = row
        time.sleep(0.15)          # be polite to the free API
    return sorted(by_id.values(), key=lambda g: (g["game_date"], g["game_id"]))


def standings(on_date: date | None = None) -> list[dict[str, Any]]:
    """The league table on a date (defaults to today)."""
    stamp = (on_date or date.today()).isoformat()
    payload = get_json(f"{WEB_API}/standings/{stamp}")
    return payload.get("standings", [])


def club_stats(season: int) -> dict[str, dict[str, float]]:
    """Season totals per club: the numbers behind the matchup comparison bars."""
    summary = get_json(
        f"{STATS_API}/team/summary?cayenneExp=seasonId={season}%20and%20gameTypeId=2"
    )
    directory = get_json(f"{STATS_API}/team")
    code_of = {t["fullName"]: t["triCode"] for t in directory.get("data", [])}

    out: dict[str, dict[str, float]] = {}
    for row in summary.get("data", []):
        code = code_of.get(row.get("teamFullName", ""))
        if not code:
            continue
        out[code] = {
            "goalsFor": round(row.get("goalsForPerGame") or 0, 2),
            "goalsAgainst": round(row.get("goalsAgainstPerGame") or 0, 2),
            "powerPlay": round((row.get("powerPlayPct") or 0) * 100, 1),
            "penaltyKill": round((row.get("penaltyKillPct") or 0) * 100, 1),
            "shotsPerGame": round(row.get("shotsForPerGame") or 0, 1),
            "shotsAgainst": round(row.get("shotsAgainstPerGame") or 0, 1),
            "faceoffWin": round((row.get("faceoffWinPct") or 0) * 100, 1),
            "gamesPlayed": int(row.get("gamesPlayed") or 0),
        }
    return out


# The 32 clubs of the current NHL. Kept as a constant so the refresh job
# does not need an extra API call just to learn who is playing.
DEFAULT_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK",
    "WPG", "WSH",
]


def parse_date(text: str) -> date:
    return datetime.strptime(text[:10], "%Y-%m-%d").date()
