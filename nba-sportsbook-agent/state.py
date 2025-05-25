from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd
import pickle


############# Odds API #############
class BetOutcome:
    def __init__(self, name: str, price: float, point: Optional[float] = None, description: Optional[str] = None):
        self.name = name
        self.price = price
        self.point = point
        self.description = description

    def __repr__(self):
        return f"BetOutcome(name={self.name}, price={self.price}, point={self.point}, description={self.description})"


class BetMarket:
    def __init__(self, key: str, outcomes: List[BetOutcome]):
        self.key = key
        self.outcomes = outcomes

    def __repr__(self):
        return f"BetMarket(key={self.key}, outcomes={len(self.outcomes)})"


def default_dict_of_lists():
    return defaultdict(list)


class BetMarketGroup:
    def __init__(self):
        self.markets: Dict[str, BetMarket] = {}
        self.description_index: Dict[str, Dict[str, List[BetOutcome]]] = defaultdict(default_dict_of_lists)

    def add_market(self, key: str, market: BetMarket):
        self.markets[key] = market
        for outcome in market.outcomes:
            # Use 'description' if available (player/team), else fall back to 'name' (e.g. for spreads)
            ref = outcome.description or outcome.name
            if ref:
                self.description_index[ref][key].append(outcome)

    def get_market(self, key: str) -> Optional[BetMarket]:
        return self.markets.get(key)

    def get_outcomes_for(self, entity: str) -> Dict[str, List[BetOutcome]]:
        return self.description_index.get(entity, {})

    def get_all_descriptions(self) -> List[str]:
        return list(self.description_index.keys())

    def __repr__(self):
        return f"BetMarketGroup(markets={list(self.markets.keys())})"


class BetEvent:
    def __init__(self, event_data: dict):
        self.event_id = event_data["id"]
        self.home_team = event_data["home_team"]
        self.away_team = event_data["away_team"]
        self.bookmakers = event_data["bookmakers"]

        self.player_markets = BetMarketGroup()
        self.team_markets = BetMarketGroup()
        self.match_markets = BetMarketGroup()

        self._process_bookmakers()

    def _process_bookmakers(self):
        # TODO: Supporting only one broker now
        for market_data in self.bookmakers[0]["markets"]:
            key = market_data["key"]
            outcomes = [BetOutcome(**o) for o in market_data["outcomes"]]
            market = BetMarket(key, outcomes)

            if key.startswith("player_"):
                self.player_markets.add_market(key, market)
            elif key in {"alternate_team_totals", "team_totals"}:
                self.team_markets.add_market(key, market)
            elif key in {"spreads", "alternate_spreads"}:
                self.team_markets.add_market(key, market)
            else:
                self.match_markets.add_market(key, market)

    def get_player_market(self, player_name: str) -> Dict[str, List[BetOutcome]]:
        return self.player_markets.get_outcomes_for(player_name)

    def get_team_market(self, team_name: str) -> Dict[str, List[BetOutcome]]:
        return self.team_markets.get_outcomes_for(team_name)

    def get_match_markets(self) -> BetMarketGroup:
        return self.match_markets

    def get_all_player_names(self) -> List[str]:
        return self.player_markets.get_all_descriptions()

    def get_all_team_names(self) -> List[str]:
        return self.team_markets.get_all_descriptions()

    def get_teams(self) -> List[str]:
        return [self.home_team, self.away_team]

    def __repr__(self):
        return f"BetEvent(event_id={self.event_id}, teams={self.home_team} vs {self.away_team})"


def load_events(events_data: List[dict]) -> Dict[str, BetEvent]:
    return {event_data["id"]: BetEvent(event_data) for event_data in events_data}



############# Metadata Agent #############
@dataclass(frozen=True)
class TeamInfo:
	nba_team_id: str
	odds_team_name: str


@dataclass(frozen=True)
class PlayerInfo:
	nba_player_id: str
	odds_player_name: str


@dataclass(frozen=True)
class GameInfo:
	nba_game_id: str
	odds_game_id: str


@dataclass
class GameDetails:
	game_info: GameInfo
	home_team_info: TeamInfo
	away_team_info: TeamInfo
	players_info: List[PlayerInfo]


############# Data Agent #############
##### NBA Games #####
@dataclass(frozen=True)
class NBATeamInfo:
	nba_team_id: str
	nba_team_name: str


@dataclass(frozen=True)
class NBAPlayerInfo:
	nba_player_id: str
	nba_player_name: str


@dataclass
class GlobalState:
	user_query: str
	final_answer: Optional[str] = None

	game_details: Optional[GameDetails] = None

	upcoming_games: Dict[str, Dict[NBATeamInfo, List[NBAPlayerInfo]]] = field(default_factory=dict)
	player_stats: Dict[str, pd.DataFrame] = field(default_factory=dict)
	upcoming_bets: Dict[str, BetEvent] = field(default_factory=dict)
	
	required_data_loaded: bool = False

	def save_global_state(self, filepath: str) -> None:
		with open(filepath, 'wb') as f:
			pickle.dump(self, f)

	def load_global_state(filepath: str) -> "GlobalState":
		with open(filepath, 'rb') as f:
			state = pickle.load(f)
		return state

	def summarize_state_for_data_agent(self):
		if not self.upcoming_games:
			return "Don't have any information about upcoming games, teams, and players from NBA site."

		if not self.upcoming_bets:
			return "Don't have any information about upcoming bets for the NBA games."

		summary = "Upcoming Games in NBA from the website:\n"
		for game_id, teams in self.upcoming_games.items():
			summary += f"nba_game_id: {game_id}\n"
			for team_info, players in teams.items():
				summary += f"  Team in NBA: {team_info.nba_team_name} (nba_team_id: {team_info.nba_team_id})\n"
				if players:
					for player in players:
						summary += f"    - {player.nba_player_name} (nba_player_id: {player.nba_player_id})\n"
		summary += "\n"

		if self.player_stats:
			summary += "Player Stats available for player ids:\n"
			for player_id, df in self.player_stats.items():
				summary += f"  - {player_id}\n"
			summary += "\n"

		summary += "Bets for the upcoming NBA games from Odds API (betting odds, markets are also available for each player but just not displayed here):\n"
		for bet_event_id, bet_event in self.upcoming_bets.items():
			summary += f"bet_event_id: {bet_event_id}; {bet_event.home_team} vs {bet_event.away_team}\n"
			summary += f"  Available player names in player market bets:\n"
			for player_name in bet_event.get_all_player_names():
				summary += f"    - {player_name}\n"

		return summary
