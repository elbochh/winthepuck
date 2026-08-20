from __future__ import annotations

import argparse
import logging

from config import PROCESSED_DIR, RAW_DIR, current_date, ensure_directories
from src.build_features import build_model_features
from src.build_live_win_probability import build_current_live_features, build_live_win_probability_dataset
from src.build_merged_data import build_merged_model_data
from src.fetch_boxscores import flatten_boxscores
from src.fetch_games import completed_games, fetch_completed_game_artifacts
from src.fetch_goalie_stats import fetch_goalie_stats
from src.fetch_live import fetch_live_data
from src.fetch_play_by_play import flatten_play_by_play
from src.fetch_player_stats import fetch_player_stats
from src.fetch_rosters import fetch_rosters
from src.fetch_schedule import fetch_season_schedules, fetch_upcoming, split_upcoming, write_games_csv
from src.fetch_seasons import fetch_active_team_abbrevs, resolve_season_range
from src.fetch_standings import fetch_standings
from src.fetch_team_stats import fetch_team_stats
from src.nhl_client import NHLClient
from src.utils import count_duplicate_game_ids, count_missing_game_files, load_csv, setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NHL public API data ingestion pipeline")
    parser.add_argument(
        "--mode",
        choices=[
            "historical",
            "upcoming",
            "live",
            "build-features",
            "build-live-features",
            "build-current-live",
            "build-merged",
            "all",
        ],
        required=True,
    )
    parser.add_argument("--start-season", type=int, default=None)
    parser.add_argument("--end-season", type=int, default=None)
    parser.add_argument("--days-ahead", type=int, default=14)
    parser.add_argument("--max-games", type=int, default=None)
    parser.add_argument("--force-refresh", action="store_true")
    return parser.parse_args()


def run_historical(client: NHLClient, start_season: int | None, end_season: int | None) -> None:
    seasons = resolve_season_range(client, start_season, end_season)
    all_games = []
    all_active_teams: set[str] = set()
    games_per_season: dict[int, int] = {}

    for season in seasons:
        teams = fetch_active_team_abbrevs(client, season)
        all_active_teams.update(teams)
        games = fetch_season_schedules(client, season, teams)
        games_per_season[season] = len(games)
        all_games.extend(games)

    games_df = write_games_csv(all_games)
    split_upcoming(games_df)
    fetch_completed_game_artifacts(client, games_df)
    flatten_boxscores(completed_games(games_df))
    flatten_play_by_play(completed_games(games_df))
    fetch_standings(client, seasons, current_date())
    fetch_rosters(client, sorted(all_active_teams))
    fetch_team_stats(client, seasons)
    fetch_player_stats(client, seasons)
    fetch_goalie_stats(client, seasons)

    print("Games fetched per season:")
    for season, count in games_per_season.items():
        print(f"  {season}: {count}")


def run_upcoming(client: NHLClient, days_ahead: int) -> None:
    upcoming = fetch_upcoming(client, current_date(), days_ahead)
    print(f"Upcoming games: {len(upcoming)}")


def run_live(client: NHLClient) -> None:
    games = fetch_live_data(client, current_date())
    current_features = build_current_live_features()
    print(f"Live/schedule games discovered: {len(games)}")
    print(f"Current live feature rows: {len(current_features)}")


def run_build_features() -> bool:
    df, leakage_ok = build_model_features()
    print(f"Model feature rows: {len(df)}")
    print(f"Model feature leakage validation: {'PASS' if leakage_ok else 'FAIL'}")
    return leakage_ok


def run_build_merged() -> None:
    df = build_merged_model_data()
    print(f"Merged model data rows: {len(df)}")


def run_build_live_features(
    start_season: int | None = None,
    end_season: int | None = None,
    max_games: int | None = None,
) -> None:
    df = build_live_win_probability_dataset(
        start_season=start_season,
        end_season=end_season,
        max_games=max_games,
    )
    print(f"Live win-probability feature rows: {len(df)}")


def print_quality_checks(leakage_ok: bool | None = None) -> None:
    games = load_csv(PROCESSED_DIR / "games.csv")
    completed = completed_games(games) if not games.empty else games
    upcoming = load_csv(PROCESSED_DIR / "upcoming_games.csv")
    duplicate_count = count_duplicate_game_ids(PROCESSED_DIR / "games.csv")
    missing_boxscores = count_missing_game_files(RAW_DIR / "games", completed, "boxscore.json")
    missing_pbp = count_missing_game_files(RAW_DIR / "games", completed, "play_by_play.json")

    print("Quality checks:")
    print(f"  Missing boxscores: {missing_boxscores}")
    print(f"  Missing play-by-play files: {missing_pbp}")
    print(f"  Upcoming games: {len(upcoming)}")
    print(f"  Duplicate game_id rows in games.csv: {duplicate_count}")
    if leakage_ok is None:
        print("  Model feature leakage validation: not run")
    else:
        print(f"  Model feature leakage validation: {'PASS' if leakage_ok else 'FAIL'}")


def main() -> None:
    ensure_directories()
    setup_logging()
    args = parse_args()
    client = NHLClient(force_refresh=args.force_refresh)
    leakage_ok: bool | None = None

    logging.info("Starting mode=%s", args.mode)
    if args.mode == "historical":
        run_historical(client, args.start_season, args.end_season)
    elif args.mode == "upcoming":
        run_upcoming(client, args.days_ahead)
    elif args.mode == "live":
        run_live(client)
    elif args.mode == "build-features":
        leakage_ok = run_build_features()
    elif args.mode == "build-live-features":
        run_build_live_features(args.start_season, args.end_season, args.max_games)
    elif args.mode == "build-current-live":
        current_features = build_current_live_features()
        print(f"Current live feature rows: {len(current_features)}")
    elif args.mode == "build-merged":
        run_build_merged()
    elif args.mode == "all":
        run_historical(client, args.start_season, args.end_season)
        run_upcoming(client, args.days_ahead)
        run_live(client)
        leakage_ok = run_build_features()
        run_build_live_features(args.start_season, args.end_season, args.max_games)
        run_build_merged()
    print_quality_checks(leakage_ok)


if __name__ == "__main__":
    main()
