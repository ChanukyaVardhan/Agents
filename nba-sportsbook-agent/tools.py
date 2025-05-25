from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any, List
import nba_stats, odds
from utils import logger
import json
import os
import state
import time


BETS_CACHE_DIR = "cache/bets"


class Tool:
    def __init__(
        self,
        name: str,
        func: Callable,
        tool_description: str,
        tool_inputs: Optional[Dict[str, str]] = None,
        tool_outputs: Optional[str] = None,
    ):
        self.name = name
        self.func = func
        self.tool_description = tool_description
        self.tool_inputs = tool_inputs or {}
        self.tool_outputs = tool_outputs or "No specific output format documented."

    def use(self, input: Any = None):
        try:
            if self.tool_inputs and isinstance(input, dict):
                return self.func(**input)
            elif self.tool_inputs and isinstance(input, str):
                return self.func(input)
            else:
                return self.func()
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {e}")
            return str(e)

    def describe(self) -> str:
        input_lines = "\n    ".join(f"{k}: {v}" for k, v in self.tool_inputs.items()) if self.tool_inputs else "None"
        return f"""- {self.name}: {self.tool_description}
  Inputs:
    {input_lines}
  Output:
    {self.tool_outputs}
"""


def load_upcoming_nba_games_and_bets(days_ahead=1):
	upcoming_nba_games = load_upcoming_nba_games(days_ahead)
	upcoming_nba_bets = load_upcoming_nba_bets(days_ahead)

	return (upcoming_nba_games, upcoming_nba_bets)


def load_upcoming_nba_games(days_ahead=1) -> Dict[str, Dict[state.NBATeamInfo, List[state.NBAPlayerInfo]]]:
	upcoming_games = defaultdict(dict)

	# Get static info
	teams_df = nba_stats.get_teams()
	players_df = nba_stats.get_all_players()

	# Get upcoming game data
	games_df = nba_stats.get_upcoming_games(days_ahead=days_ahead)
	if games_df.empty:
		return {}

	for _, row in games_df.iterrows():
		game_id = row["GAME_ID"]
		home_team_id = row["HOME_TEAM_ID"]
		away_team_id = row["VISITOR_TEAM_ID"]

		for team_id in [home_team_id, away_team_id]:
			team_row = teams_df[teams_df["id"] == team_id]
			if team_row.empty:
				continue
			team_name = team_row.iloc[0]["full_name"]

			team_info = state.NBATeamInfo(nba_team_id=str(team_id), nba_team_name=team_name)

			# Get players for team
			try:
				team_roster_df = nba_stats.get_team_players(team_id)
			except Exception as e:
				raise RuntimeError(f"Failed to get players for team_id {team_id}: {e}")

			player_infos = []
			for _, player_row in team_roster_df.iterrows():
				player_infos.append(
					state.NBAPlayerInfo(
						nba_player_id=str(player_row["PLAYER_ID"]),
						nba_player_name=player_row["PLAYER"]
					)
				)

			upcoming_games[str(game_id)][team_info] = player_infos

	return dict(upcoming_games)


def load_players_stats(player_ids: List[str]):
	player_stats_dict = {}

	for player_id in player_ids:
		try:
			stats_df = nba_stats.get_player_stats(player_id)
			player_stats_dict[player_id] = stats_df
			time.sleep(1.1)  # Respect NBA API rate limits
		except Exception as e:
			raise RuntimeError(f"Error fetching stats for player ID {player_id}: {e}")

	return player_stats_dict


def load_upcoming_nba_bets(days_ahead=1, use_cache=True) -> dict:
    """
    Loads upcoming NBA events and returns a mapping from event_id to Event instance.
    Uses a local cache per date and per event to minimize redundant API calls.
    """
    target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    date_dir = os.path.join(BETS_CACHE_DIR, target_date)
    os.makedirs(date_dir, exist_ok=True)

    # Load or fetch summary events list
    events_list_path = os.path.join(date_dir, "events_list.json")
    if use_cache and os.path.exists(events_list_path):
        logger.info(f"Loading cached event list from {events_list_path}")
        with open(events_list_path, "r") as f:
            events_data = json.load(f)
    else:
        logger.info(f"Fetching event list for {target_date}")
        events_data = odds.get_sports_events(days_ahead=days_ahead)
        with open(events_list_path, "w") as f:
            json.dump(events_data, f, indent=2)
        logger.info(f"Saved event list to {events_list_path}")

    # Load or fetch individual event data
    event_map = {}
    for event_meta in events_data:
        event_id = event_meta["id"]
        event_path = os.path.join(date_dir, f"{event_id}.json")

        if use_cache and os.path.exists(event_path):
            logger.info(f"Loading cached event data for {event_id}")
            with open(event_path, "r") as f:
                detailed_event = json.load(f)
        else:
            logger.info(f"Fetching detailed odds for event {event_id}")
            detailed_event = odds.get_event_odds(event_id=event_id, sport="basketball_nba")
            if not detailed_event:
                logger.warning(f"No detailed data for event {event_id}")
                continue
            with open(event_path, "w") as f:
                json.dump(detailed_event, f, indent=2)
            logger.info(f"Cached detailed event to {event_path}")

        try:
            event_obj = state.BetEvent(detailed_event)
            event_map[event_id] = event_obj
        except Exception as e:
            raise RuntimeError(f"Error parsing event {event_id}: {e}")

    logger.info("Finished loading upcoming bets.")
    return event_map

# print(load_upcoming_nba_bets(use_cache=False))
