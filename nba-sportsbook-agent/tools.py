from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from nba_stats import NBAStatsAPI
from odds import OddsAPIClient
from typing import Callable, Optional, Dict, Any, List
from utils import logger
import json
import os
import state
import time

load_dotenv()


nba_stats_client = NBAStatsAPI()
odds_api_client = OddsAPIClient()
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

    def use(self, input_data: Any = None):
        try:
            if self.tool_inputs and isinstance(input_data, dict):
                return self.func(**input_data)
            elif self.tool_inputs and input_data is not None:
                return self.func(input_data)
            else:
                return self.func()
        except Exception as e:
            logger.error(f"Error executing tool {self.name} with input '{input_data}': {e}", exc_info=True)
            return f"Error in tool {self.name}: {str(e)}"

    def describe(self) -> str:
        input_lines = "\n    ".join(f"{k}: {v}" for k, v in self.tool_inputs.items()) if self.tool_inputs else "None"
        return f"""- {self.name}: {self.tool_description}
  Inputs:
    {input_lines}
  Output:
    {self.tool_outputs}
"""

def load_upcoming_nba_games_and_bets(days_ahead: int = 1):
    logger.info(f"Loading upcoming NBA games and bets for {days_ahead} days ahead.")
    upcoming_nba_games = load_upcoming_nba_games(days_ahead)
    upcoming_nba_bets = load_upcoming_nba_bets(days_ahead)
    # Consider adding more robust error checking here if either call fails partially.
    return upcoming_nba_games, upcoming_nba_bets

def load_upcoming_nba_games(days_ahead: int = 1):
    logger.info(f"Loading upcoming NBA games for {days_ahead} days ahead using NBAStatsAPI.")
    upcoming_games_map = defaultdict(dict)

    # Get static team info (used for mapping IDs to names)
    teams_df = nba_stats_client.get_teams()
    if teams_df.empty:
        logger.error("Failed to load NBA teams static data. Cannot proceed with loading games.")
        raise
    
    # players_df = nba_stats_client.get_all_players() # This was in original, but not used. Removed for now.

    # Get upcoming game data
    games_df = nba_stats_client.get_upcoming_games(days_ahead=days_ahead)
    if games_df.empty:
        logger.info("No upcoming NBA games found by NBAStatsAPI.")
        return {}

    for _, row in games_df.iterrows():
        game_id = str(row["GAME_ID"])
        home_team_id = row["HOME_TEAM_ID"]
        away_team_id = row["VISITOR_TEAM_ID"]

        for team_id_int in [home_team_id, away_team_id]:
            team_id_str = str(team_id_int)
            team_row_df = teams_df[teams_df["id"] == team_id_int] # Match by integer ID from games_df
            
            if team_row_df.empty:
                logger.error(f"Team ID {team_id_int} not found in static teams data for game {game_id}. Skipping team.")
                raise
            team_name = team_row_df.iloc[0]["full_name"]

            team_info = state.NBATeamInfo(nba_team_id=team_id_str, nba_team_name=team_name)

            # Get players for team
            team_roster_df = nba_stats_client.get_team_players(team_id=team_id_int) # Use integer team_id
            if team_roster_df.empty:
                logger.error(f"Failed to get player roster for team_id {team_id_int} in game {game_id}. Skipping players for this team.")
                # Still add team info, but with empty player list
                upcoming_games_map[game_id][team_info] = []
                raise

            player_infos = []
            for _, player_row in team_roster_df.iterrows():
                player_infos.append(
                    state.NBAPlayerInfo(
                        nba_player_id=str(player_row["PLAYER_ID"]),
                        nba_player_name=player_row["PLAYER"] # Assuming 'PLAYER' is the name column
                    )
                )
            upcoming_games_map[game_id][team_info] = player_infos
    
    logger.info(f"Successfully processed {len(upcoming_games_map)} upcoming NBA games.")
    return dict(upcoming_games_map)

def load_players_stats(player_ids: List[str]):
    logger.info(f"Loading player stats for player IDs: {player_ids} using NBAStatsAPI.")
    player_stats_dict = {}

    for player_id_str in player_ids:
        try:
            player_id_int = int(player_id_str) # NBAStatsAPI expects int for player_id
            stats_df = nba_stats_client.get_player_stats(player_id_int)
            if not stats_df.empty:
                player_stats_dict[player_id_str] = stats_df
                logger.debug(f"Successfully fetched stats for player ID {player_id_str}.")
            else:
                logger.error(f"No stats returned for player ID {player_id_str}.")
                raise
            # Respect NBA API rate limits - keep the sleep
            time.sleep(1.1) 
        except ValueError:
            logger.error(f"Invalid player ID format: '{player_id_str}'. Must be convertible to int.")
            raise

    logger.info(f"Finished fetching stats for {len(player_stats_dict)} out of {len(player_ids)} requested players.")
    return player_stats_dict

def load_upcoming_nba_bets(days_ahead: int = 1, use_cache: bool = True):
    logger.info(f"Loading upcoming NBA bets for {days_ahead} days ahead using OddsAPIClient. Cache enabled: {use_cache}.")
    os.makedirs(BETS_CACHE_DIR, exist_ok=True)
    
    current_processing_date_str = datetime.now().strftime("%Y-%m-%d")
    date_dir = os.path.join(BETS_CACHE_DIR, current_processing_date_str)
    os.makedirs(date_dir, exist_ok=True)

    events_list_path = os.path.join(date_dir, "events_list.json")
    
    events_data = []
    if use_cache and os.path.exists(events_list_path):
        logger.info(f"Loading cached event list from {events_list_path}")
        try:
            with open(events_list_path, "r") as f:
                events_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding cached event list {events_list_path}: {e}. Fetching live data.")
            raise

    if not events_data: # Fetch if cache miss, empty, or failed to load
        logger.info(f"Fetching live event list (days_ahead={days_ahead}).")
        events_data = odds_api_client.get_sports_events(days_ahead=days_ahead) 
        if events_data:
            try:
                with open(events_list_path, "w") as f:
                    json.dump(events_data, f, indent=2)
                logger.info(f"Saved event list to {events_list_path}")
            except IOError as e:
                logger.error(f"Error saving event list to {events_list_path}: {e}")
                raise
        else:
            logger.debug("No events data fetched from API. Cannot proceed with loading bets.")
            return {}


    event_map = {}
    for event_meta in events_data:
        event_id = event_meta.get("id")
        if not event_id:
            logger.error(f"Skipping event with missing ID in events_data: {event_meta}")
            raise
            
        # Individual event cache is within the date_dir of the *processing date*
        event_path = os.path.join(date_dir, f"{event_id}.json")
        detailed_event_data = None

        if use_cache and os.path.exists(event_path):
            logger.info(f"Loading cached event data for {event_id} from {event_path}")
            try:
                with open(event_path, "r") as f:
                    detailed_event_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding cached event data {event_path} for event {event_id}: {e}. Fetching live data.")
                raise

        if not detailed_event_data: # Fetch if cache miss, empty, or failed to load
            logger.info(f"Fetching live detailed odds for event {event_id}")
            detailed_event_data = odds_api_client.get_event_odds(event_id=event_id, sport="basketball_nba")
            if detailed_event_data: # Only save if data was successfully fetched
                try:
                    with open(event_path, "w") as f:
                        json.dump(detailed_event_data, f, indent=2)
                    logger.info(f"Cached detailed event to {event_path}")
                except IOError as e:
                    logger.error(f"Error saving detailed event {event_id} to {event_path}: {e}")
                    raise
            else:
                logger.warning(f"No detailed odds data fetched for event {event_id}. Skipping.")
                raise
        
        try:
            event_obj = state.BetEvent(detailed_event_data)
            event_map[event_id] = event_obj
        except Exception as e:
            logger.error(f"Error parsing or validating event data for {event_id}: {e}. Data: {detailed_event_data}", exc_info=True)
            raise

    logger.info(f"Finished loading upcoming bets. {len(event_map)} events processed.")
    return event_map

# print(load_upcoming_nba_bets(use_cache=False))
