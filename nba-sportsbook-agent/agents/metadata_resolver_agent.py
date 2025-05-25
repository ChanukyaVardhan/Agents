from llm import LLMClient
from pydantic import BaseModel, Field
from state import GlobalState, GameDetails, GameInfo, TeamInfo, PlayerInfo, NBATeamInfo, NBAPlayerInfo
from typing import List, Dict, Optional
from utils import logger, write_to_file
import json


PROMPT = """
You are a Metadata Resolver Agent in an NBA sportsbook system. Your task is to reconcile and link data between two sources:

1. The **NBA API**, which contains information about NBA games, teams, and players.
2. The **Odds (Betting) API**, which provides betting events and markets, including team and player names.

Your goal is to:
- Use the **user query** to identify the game the user is most interested in.
- Select the matching NBA game and betting event.
- Construct a `GameDetails` object mapping identifiers across both systems.

---

### User Query:
{query}

### NBA Games:
Each entry includes a game_id, teams, and players.

{nba_games_json}

### Betting Events:
Each entry includes an event_id, teams, and player names.

{betting_events_json}

---

### Instructions:
1. From the user query, infer which game is most relevant (based on team names, player names, or date).
2. Match the NBA game with the betting event based on teams playing the event. Confirm the mapping.
3. Map NBA team IDs to their corresponding betting team names. Use string similarity or team names to infer this.
4. Match NBA player IDs to betting player names only for the ones the user requested for if any. The names may differ slightly (e.g., abbreviations, accents). Use fuzzy matching or educated reasoning. Some NBA players may not appear in the betting event — that’s okay. Identify all the mappings you can.
5. Create a JSON object containing:
   - `game_info`: mapping between nba_game_id and odds_game_id.
   - `home_team_info`: mapping between home_team_id and odds_home_team.
   - `away_team_info`: mapping between away_team_id and odds_away_team.
   - `players_info`: list of mappings between nba_player_id and odds_player_name for matched players.

### Format your response as JSON if you found a match. Respond only in this json format (don't add any comments in your response):
```json
{{
  "thought": "Your complete thought process in coming up with this conclusion.",
  "answer": {{
    "game_info": {{
      "nba_game_id": "...",
      "odds_game_id": "..."
    }},
    "home_team_info": {{
      "nba_team_id": "...",
      "odds_team_name": "..."
    }},
    "away_team_info": {{
      "nba_team_id": "...",
      "odds_team_name": "..."
    }},
    "players_info": [
      {{"nba_player_id": "...", "odds_player_name": "..."}},
      ...
    ]
  }}
}}
"""

class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender.")
    content: str = Field(..., description="The content of the message.")


class MetadataAgent:
    def __init__(self, output_trace_path: str):
        self.template = self.load_template()
        self.output_trace_path = output_trace_path

        self.llm_client = LLMClient()

    def load_template(self) -> str:
        return PROMPT

    def trace(self, role: str, content: str) -> None:
        write_to_file(path=self.output_trace_path, content=f"{role}: {content}\n")

    def ask_llm(self, prompt: str) -> str:
        self.trace("user", prompt)
        contents = [Message(role='user', content=prompt)]
        response = self.llm_client.get_response(contents)

        return str(response) if response else "No response from LLM"

    def build_prompt(self, state: GlobalState) -> str:
        nba_games_json = []
        for game_id, teams in state.upcoming_games.items():
            entry = {
                "nba_game_id": game_id,
                "teams": [],
            }
            for team, players in teams.items():
                entry["teams"].append({
                    "nba_team_id": team.nba_team_id,
                    "nba_team_name": team.nba_team_name,
                    "players": [
                        {
                            "nba_player_id": p.nba_player_id,
                            "nba_player_name": p.nba_player_name
                        } for p in players
                    ]
                })
            nba_games_json.append(entry)

        betting_events_json = []
        for event in state.upcoming_bets.values():
            betting_events_json.append({
                "odd_game_id": event.event_id,
                "home_team": event.home_team,
                "away_team": event.away_team,
                "player_names": event.get_all_player_names()
            })

        return self.template.format(
            nba_games_json=json.dumps(nba_games_json, indent=2),
            betting_events_json=json.dumps(betting_events_json, indent=2),
            query=state.user_query
        )

    def parse_game_details(self, response: str) -> GameDetails:
        cleaned = response.strip().strip('`').strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        answer = json.loads(cleaned, strict=False)
        data = answer.get("answer")

        game_info = GameInfo(**data["game_info"])
        home_team_info = TeamInfo(**data["home_team_info"])
        away_team_info = TeamInfo(**data["away_team_info"])

        players_info = [PlayerInfo(**p) for p in data.get("players_info", [])]

        return GameDetails(
            game_info=game_info,
            home_team_info=home_team_info,
            away_team_info=away_team_info,
            players_info=players_info
        )

    def execute(self, state: GlobalState) -> GlobalState:
        logger.info("MetadataAgent: Starting execution.")
        
        prompt = self.build_prompt(state)
        response = self.ask_llm(prompt)

        logger.info(f"MetadataAgent LLM response: {response}")
        self.trace("assistant", response)

        try:
            game_details = self.parse_game_details(response)
            state.game_details = game_details
        except Exception as e:
            logger.error(f"Failed to parse LLM response in MetadataAgent: {e}")
            self.trace("system", f"MetadataAgent failed to parse: {e}")

        return state
