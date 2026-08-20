"""Recent-form numbers worked out straight from the real NHL scores.

The Phase 1 data pipeline calculates about 130 inputs for every game, but most
of them need full box scores (hits, blocked shots, goalie save percentage...).
The free NHL schedule endpoint only gives us the final score, and that is
already enough to rebuild the strongest "recent form" inputs exactly the way
the pipeline does:

    last 5 / last 10 win percentage      goals for and against in the last 5
    goal difference over the last 10     points percentage this season
    home and road splits this season     head-to-head record

Doing it this way means the website's predictions keep improving all season
long without anyone having to re-run the 18 GB pipeline.
"""
from __future__ import annotations

from datetime import date

import nhl_api

# Season records restart every October. Before a team has played, these have
# no value at all - which is exactly what the model saw while it was training,
# so we leave them empty rather than inventing a number.
SEASON_FEATURES = [
    "season_points_pct_before_game",
    "home_win_pct_before_game", "road_win_pct_before_game",
    "home_goal_diff_avg_before_game", "road_goal_diff_avg_before_game",
]


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


class FormBook:
    """Keeps every finished game so we can look up any team's form on any date."""

    def __init__(self) -> None:
        self.by_team: dict[str, list[dict]] = {}
        self.by_pair: dict[tuple[str, str], list[dict]] = {}

    def add(self, game: dict) -> None:
        """Remember one finished game."""
        if not game["finished"]:
            return
        day = nhl_api.parse_date(game["game_date"])
        home, away = game["home_team"], game["away_team"]
        home_goals, away_goals = int(game["home_score"]), int(game["away_score"])

        for team, is_home, goals_for, goals_against in (
            (home, 1, home_goals, away_goals),
            (away, 0, away_goals, home_goals),
        ):
            self.by_team.setdefault(team, []).append({
                "date": day,
                "game_id": game["game_id"],
                "season": game["season"],
                "is_home": is_home,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "win": int(goals_for > goals_against),
                "overtime": game["last_period_type"] in {"OT", "SO"},
            })

        self.by_pair.setdefault(tuple(sorted((home, away))), []).append({
            "date": day,
            "game_id": game["game_id"],
            "home": home,
            "winner": home if home_goals > away_goals else away,
            "home_goals": home_goals,
            "away_goals": away_goals,
        })

    def sort(self) -> None:
        for rows in self.by_team.values():
            rows.sort(key=lambda r: (r["date"], r["game_id"]))
        for rows in self.by_pair.values():
            rows.sort(key=lambda r: (r["date"], r["game_id"]))

    # -------------------------------------------------------

    def team_features(self, team: str, game_day: date, season: int) -> dict[str, float]:
        """The form numbers for one team going into a game on `game_day`."""
        history = [r for r in self.by_team.get(team, []) if r["date"] < game_day]
        if not history:
            return {}

        last_5, last_10 = history[-5:], history[-10:]
        this_season = [r for r in history if r["season"] == season]
        home_games = [r for r in this_season if r["is_home"] == 1]
        road_games = [r for r in this_season if r["is_home"] == 0]

        gap = (game_day - history[-1]["date"]).days
        features: dict[str, float] = {
            "rest_days": float(min(gap, 14)),
            "back_to_back": 1.0 if gap == 1 else 0.0,
            "games_last_3_days": float(self._count_within(history, game_day, 3)),
            "games_last_7_days": float(self._count_within(history, game_day, 7)),
            "games_last_14_days": float(self._count_within(history, game_day, 14)),
            "last_5_win_pct": _average([r["win"] for r in last_5]),
            "last_10_win_pct": _average([r["win"] for r in last_10]),
            "last_5_goals_for_avg": _average([r["goals_for"] for r in last_5]),
            "last_5_goals_against_avg": _average([r["goals_against"] for r in last_5]),
            "goal_diff_last_10": float(
                sum(r["goals_for"] - r["goals_against"] for r in last_10)),
        }

        if this_season:
            # the pipeline counts 2 points for a win and none for a loss
            features["season_points_pct_before_game"] = round(
                sum(2 * r["win"] for r in this_season) / (2 * len(this_season)), 4)
        if home_games:
            features["home_win_pct_before_game"] = _average(
                [r["win"] for r in home_games])
            features["home_goal_diff_avg_before_game"] = _average(
                [r["goals_for"] - r["goals_against"] for r in home_games])
        if road_games:
            features["road_win_pct_before_game"] = _average(
                [r["win"] for r in road_games])
            features["road_goal_diff_avg_before_game"] = _average(
                [r["goals_for"] - r["goals_against"] for r in road_games])

        return {k: v for k, v in features.items() if v is not None}

    def head_to_head(self, home: str, away: str, game_day: date) -> dict[str, float]:
        """How these two clubs have got on against each other lately."""
        history = [r for r in self.by_pair.get(tuple(sorted((home, away))), [])
                   if r["date"] < game_day]
        if not history:
            return {"h2h_games_last_365_days": 0.0}

        last_5 = history[-5:]
        wins = [int(r["winner"] == home) for r in last_5]
        margins = []
        for row in last_5:
            if row["home"] == home:
                margins.append(row["home_goals"] - row["away_goals"])
            else:
                margins.append(row["away_goals"] - row["home_goals"])

        return {
            "h2h_games_last_365_days": float(self._count_within(history, game_day, 365)),
            "h2h_home_team_win_pct_last_5": _average(wins),
            "h2h_home_team_goal_diff_avg_last_5": _average(margins),
        }

    @staticmethod
    def _count_within(history: list[dict], game_day: date, days: int) -> int:
        return sum(1 for r in history if 0 <= (game_day - r["date"]).days <= days)


def last_five_form(book: FormBook, season: int) -> dict[str, list[str]]:
    """The W / L pills shown under each team name on the website."""
    out: dict[str, list[str]] = {}
    for team, rows in book.by_team.items():
        season_rows = [r for r in rows if r["season"] == season]
        # W = win, L = regulation loss, O = overtime or shootout loss
        out[team] = [
            "W" if r["win"] else ("O" if r["overtime"] else "L")
            for r in season_rows[-5:]
        ]
    return out
