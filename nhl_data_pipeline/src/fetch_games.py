from __future__ import annotations

from typing import Any

import pandas as pd
from tqdm import tqdm

from config import COMPLETED_GAME_STATES, RAW_DIR
from src.nhl_client import NHLClient


def completed_games(games_df: pd.DataFrame) -> pd.DataFrame:
    if games_df.empty:
        return games_df
    return games_df[games_df["game_state"].isin(COMPLETED_GAME_STATES)].copy()


def fetch_game_artifacts(client: NHLClient, game_id: int, season: int) -> dict[str, Any | None]:
    base = RAW_DIR / "games" / str(season) / str(game_id)
    return {
        "landing": client.get_web(f"gamecenter/{game_id}/landing", base / "landing.json", optional=True),
        "boxscore": client.get_web(f"gamecenter/{game_id}/boxscore", base / "boxscore.json", optional=True),
        "play_by_play": client.get_web(f"gamecenter/{game_id}/play-by-play", base / "play_by_play.json", optional=True),
        "right_rail": client.get_web(f"gamecenter/{game_id}/right-rail", base / "right_rail.json", optional=True),
        "shift_charts": client.get_stats(
            "shiftcharts",
            base / "shift_charts.json",
            params={"cayenneExp": f"gameId={game_id}"},
            optional=True,
        ),
    }


def fetch_completed_game_artifacts(client: NHLClient, games_df: pd.DataFrame) -> None:
    for row in tqdm(completed_games(games_df).itertuples(index=False), desc="Gamecenter"):
        fetch_game_artifacts(client, int(row.game_id), int(row.season))
