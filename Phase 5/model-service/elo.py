"""Elo ratings and recent-form numbers for NHL teams.

These are exactly the same rules used in Phase 2 (`nhl_model/build_model_dataset.py`),
copied here so the cloud refresh job can update the ratings on its own without
needing the 18 GB data pipeline.

The design follows FiveThirtyEight's NHL Elo:
  * K = 6 and a home-ice advantage worth 50 Elo points
  * a margin-of-victory multiplier so a 5-1 win counts more than a 2-1 win
  * every summer each team moves 30% back towards the league average (1505)
"""
from __future__ import annotations

import math

MEAN_ELO = 1505.0
K = 6.0
HFA = 50.0
SEASON_REVERSION = 0.30
PLAYOFF_MULT = 1.25
ALPHA = 0.05          # how fast the "recent form" numbers forget old games


def win_probability(elo_diff: float) -> float:
    """Turn an Elo gap into a win probability."""
    return 1.0 / (10.0 ** (-elo_diff / 400.0) + 1.0)


def mov_multiplier(goal_diff: int, elo_diff_winner: float) -> float:
    """Bigger wins move the rating more, but not without limit."""
    multiplier = 0.6686 * math.log(max(abs(goal_diff), 1)) + 0.8048
    return multiplier * (2.05 / (elo_diff_winner * 0.001 + 2.05))


class TeamState:
    """The rating and form numbers we keep for one team."""

    def __init__(self, elo: float = MEAN_ELO, decay_gd: float = 0.0,
                 decay_win: float = 0.5, season: int = 0,
                 features: dict[str, float] | None = None):
        self.elo = elo
        self.decay_gd = decay_gd
        self.decay_win = decay_win
        self.season = season
        self.features = features or {}

    def to_dict(self) -> dict:
        return {"elo": round(self.elo, 3), "decay_gd": round(self.decay_gd, 5),
                "decay_win": round(self.decay_win, 5), "season": self.season,
                "features": self.features}

    @classmethod
    def from_dict(cls, data: dict) -> "TeamState":
        return cls(data["elo"], data["decay_gd"], data["decay_win"],
                   data.get("season", 0), data.get("features", {}))


def start_new_season(state: TeamState, season: int) -> None:
    """Pull a team back towards the middle when a new season begins."""
    if state.season == season:
        return
    state.elo = MEAN_ELO + (state.elo - MEAN_ELO) * (1 - SEASON_REVERSION)
    state.decay_gd *= 0.5
    state.decay_win = 0.5 + (state.decay_win - 0.5) * 0.5
    state.season = season


def apply_result(home: TeamState, away: TeamState, home_score: int,
                 away_score: int, game_type: int) -> None:
    """Update both teams after a finished game."""
    elo_diff = home.elo + HFA - away.elo
    expected_home = win_probability(elo_diff)
    home_win = 1 if home_score > away_score else 0
    goal_diff = home_score - away_score
    winner_elo_diff = elo_diff if home_win else -elo_diff

    k = K * (PLAYOFF_MULT if game_type == 3 else 1.0)
    shift = k * mov_multiplier(goal_diff, winner_elo_diff) * (home_win - expected_home)
    home.elo += shift
    away.elo -= shift

    home.decay_gd = (1 - ALPHA) * home.decay_gd + ALPHA * goal_diff
    away.decay_gd = (1 - ALPHA) * away.decay_gd - ALPHA * goal_diff
    home.decay_win = (1 - ALPHA) * home.decay_win + ALPHA * home_win
    away.decay_win = (1 - ALPHA) * away.decay_win + ALPHA * (1 - home_win)


def matchup_features(home: TeamState, away: TeamState) -> dict[str, float]:
    """The Elo and form columns the trained model expects for one matchup."""
    return {
        "home_elo_pre": home.elo,
        "away_elo_pre": away.elo,
        "elo_diff": home.elo - away.elo,
        "elo_prob_home": win_probability(home.elo + HFA - away.elo),
        "home_decay_goal_diff": home.decay_gd,
        "away_decay_goal_diff": away.decay_gd,
        "home_decay_win_rate": home.decay_win,
        "away_decay_win_rate": away.decay_win,
        "decay_goal_diff_diff": home.decay_gd - away.decay_gd,
        "decay_win_rate_diff": home.decay_win - away.decay_win,
    }
