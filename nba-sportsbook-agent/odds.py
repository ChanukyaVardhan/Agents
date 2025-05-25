from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils import logger
import json
import os
import requests

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
ODDS_API_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

MAIN_MARKETS = [
	"h2h",
	"spreads",
	"totals",
]

ALTERNATE_MARKETS = [
	"alternate_spreads",
	"alternate_totals",
	"team_totals",
	"alternate_team_totals",
]

PLAYER_MARKETS = [
	"player_points",
	"player_points_q1",
	"player_rebounds",
	"player_rebounds_q1",
	"player_assists",
	"player_assists_q1",
	"player_threes",
	"player_blocks",
	"player_steals",
	"player_blocks_steals",
	"player_turnovers",
	"player_points_rebounds_assists",
	"player_points_rebounds",
	"player_points_assists",
	"player_rebounds_assists",
	"player_field_goals",
	"player_frees_made",
	"player_frees_attempts",
	"player_first_basket",
	"player_first_team_basket",
	"player_double_double",
	"player_triple_double",
	"player_method_of_first_basket",
	"player_points_alternate",
	"player_rebounds_alternate",
	"player_assists_alternate",
	"player_blocks_alternate",
	"player_steals_alternate",
	"player_turnovers_alternate",
	"player_threes_alternate",
	"player_points_assists_alternate",
	"player_points_rebounds_alternate",
	"player_rebounds_assists_alternate",
	"player_points_rebounds_assists_alternate",
]

ALL_MARKETS = MAIN_MARKETS + ALTERNATE_MARKETS + PLAYER_MARKETS

FAVOURITE_BOOKMAKERS = [
	"fanduel",
	# "draftkings",
	# "betmgm"
]


def get_sports():
	url = "https://api.the-odds-api.com/v4/sports"
	params = {
		"apiKey": ODDS_API_KEY
	}

	response = requests.get(url, params=params)
	if response.status_code != 200:
		logger.error(f"Failed to get sports: {response.status_code}, {response.text}")

	data = response.json()
	return data


def get_sports_events(sport="basketball_nba", days_ahead=1):
	now = datetime.utcnow()
	end_time = now + timedelta(days=days_ahead)

	# Format to "YYYY-MM-DDTHH:MM:SSZ"
	commenceTimeFrom = now.strftime(ODDS_API_TIME_FORMAT)
	commenceTimeTo = end_time.strftime(ODDS_API_TIME_FORMAT)

	url = f"https://api.the-odds-api.com/v4/sports/{sport}/events"
	params = {
		"apiKey": ODDS_API_KEY,
		"commenceTimeFrom": commenceTimeFrom,
		"commenceTimeTo": commenceTimeTo
	}

	response = requests.get(url, params=params)

	if response.status_code != 200:
		logger.error(f"Failed to get sports: {response.status_code}, {response.text}")
		return []

	return response.json()


def get_event_odds(event_id, sport="basketball_nba", markets=None, bookmakers=None):
	url = f"https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds"
	params = {
		"apiKey": ODDS_API_KEY,
		"regions": "us",
		"markets": ",".join(markets) if markets is not None else ",".join(ALL_MARKETS),
		"bookmakers": ",".join(bookmakers) if bookmakers is not None else ",".join(FAVOURITE_BOOKMAKERS)
	}

	response = requests.get(url, params=params)
	if response.status_code != 200:
		logger.error(f"Failed to get event odds: {response.status_code}, {response.text}")
		return {}

	return response.json()
