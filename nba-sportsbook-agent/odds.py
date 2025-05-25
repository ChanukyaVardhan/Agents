from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils import logger
import json
import os
import requests

load_dotenv()


class OddsAPIClient:
    ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
    ODDS_API_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

    MAIN_MARKETS = ["h2h", "spreads", "totals"]
    ALTERNATE_MARKETS = ["alternate_spreads", "alternate_totals", "team_totals", "alternate_team_totals"]
    PLAYER_MARKETS = [
        "player_points", "player_points_q1", "player_rebounds", "player_rebounds_q1",
        "player_assists", "player_assists_q1", "player_threes", "player_blocks",
        "player_steals", "player_blocks_steals", "player_turnovers",
        "player_points_rebounds_assists", "player_points_rebounds", "player_points_assists",
        "player_rebounds_assists", "player_field_goals", "player_frees_made",
        "player_frees_attempts", "player_first_basket", "player_first_team_basket",
        "player_double_double", "player_triple_double", "player_method_of_first_basket",
        "player_points_alternate", "player_rebounds_alternate", "player_assists_alternate",
        "player_blocks_alternate", "player_steals_alternate", "player_turnovers_alternate",
        "player_threes_alternate", "player_points_assists_alternate",
        "player_points_rebounds_alternate", "player_rebounds_assists_alternate",
        "player_points_rebounds_assists_alternate",
    ]
    ALL_MARKETS = MAIN_MARKETS + ALTERNATE_MARKETS + PLAYER_MARKETS
    FAVOURITE_BOOKMAKERS = [
       "fanduel",
       # "draftkings",
       # "betmgm"
    ]

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            logger.error("ODDS_API_KEY not found in environment variables or provided during instantiation.")
            raise ValueError("ODDS_API_KEY is required to use OddsAPIClient.")
        
        logger.info("OddsAPIClient initialized successfully.")

    def get_sports(self):
        url = f"{self.ODDS_API_BASE_URL}/sports"
        params = {"apiKey": self.api_key}
        
        logger.debug(f"Fetching sports from URL: {url}")
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            logger.info(f"Successfully fetched {len(data)} sports.")
            return data
        except Exception as e:
            logger.error(f"An error occurred while fetching sports: {e}. URL: {url}", exc_info=True)
            raise

    def get_sports_events(self, sport="basketball_nba", days_ahead=1):
        now = datetime.utcnow()
        end_time = now + timedelta(days=days_ahead)

        commence_time_from = now.strftime(self.ODDS_API_TIME_FORMAT)
        commence_time_to = end_time.strftime(self.ODDS_API_TIME_FORMAT)

        url = f"{self.ODDS_API_BASE_URL}/sports/{sport}/events"
        params = {
            "apiKey": self.api_key,
            "commenceTimeFrom": commence_time_from,
            "commenceTimeTo": commence_time_to
        }

        logger.debug(f"Fetching events for sport '{sport}' from URL: {url} with params: {params}")
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully fetched {len(data)} events for sport '{sport}'.")
            return data
        except Exception as e:
            logger.error(f"An error occurred while fetching events for sport '{sport}': {e}. URL: {url}", exc_info=True)
            raise

    def get_event_odds(self, event_id, sport="basketball_nba", markets=None, bookmakers=None):
        url = f"{self.ODDS_API_BASE_URL}/sports/{sport}/events/{event_id}/odds"
        
        markets_str = ",".join(markets) if markets is not None else ",".join(self.ALL_MARKETS)
        bookmakers_str = ",".join(bookmakers) if bookmakers is not None else ",".join(self.FAVOURITE_BOOKMAKERS)
        
        params = {
            "apiKey": self.api_key,
            "regions": "us", # Assuming US region as per original
            "markets": markets_str,
            "bookmakers": bookmakers_str
        }

        logger.debug(f"Fetching odds for event_id '{event_id}' (sport: '{sport}') from URL: {url} with params: {params}")
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully fetched odds for event_id '{event_id}'.")
            return data
        except Exception as e:
            logger.error(f"An error occurred while fetching odds for event_id '{event_id}': {e}. URL: {url}", exc_info=True)
            return {}
