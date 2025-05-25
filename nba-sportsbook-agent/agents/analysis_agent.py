from llm import LLMClient
from pydantic import BaseModel, Field
from state import GlobalState
from tools import Tool
from typing import Callable, Dict, List, Optional
from utils import logger, write_to_file
import json
import tools as t


PROMPT = """
You are an NBA Sportsbook agent designed to provide betting-relevant insights.

Query: {query}

Your goal is to answer the query, determine the most effective course of action to address it using the presented data, reasoning, previous observations.

You must reason carefully over this data to produce high-confidence, insight-driven answers that could support betting decisions (e.g., identifying player markets with high value, team trends, or same-game parlays). You do not have access to tools. You must rely entirely on the information provided.

{game_details}

{history}

Instructions:
1. Analyze the query, previous reasoning steps, observations, and the data.
2. Decide on the next course of action.
3. Respond in the following JSON format:

If not ready to answer:
{{
    "thought": "Detailed reasoning about what the query requires, what you are analyzing, and what you're thinking through."
}}

If you have enough information to answer the query:
{{
    "thought": "Your final reasoning process",
    "answer": "Your comprehensive answer to the query"
}}

Guidelines:
- Be thorough in your reasoning.
- Always base your reasoning on the actual observations.
- Prioritize insights that assist betting decisions (e.g., team trends, player hot streaks, stats).
- Make sure to account for the number of minutes played by players with respect to the stats.
- Give high importance to player performance of players in recent 10 games over past games.
- Be transparent when data is insufficient or inconclusive.
- Do not guess; rely only on verifiable data or acknowledge uncertainty.
- Provide a final answer only when you're confident you have sufficient information.
- If presented data is not sufficient to answer the user query, answer with the data you have and what additional data you require.
"""


def decimal_to_american_odds(decimal_odds):
    if decimal_odds < 1.01:
        raise ValueError("Decimal odds must be at least 1.01")
    
    # Convert to American
    if decimal_odds >= 2.0:
        american = int((decimal_odds - 1) * 100)
        american_str = f"+{american}"
    else:
        american = int(-100 / (decimal_odds - 1))
        american_str = f"{american}"
    
    return american_str


class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender.")
    content: str = Field(..., description="The content of the message.")


class AnalysisAgent:

    def __init__(self, output_trace_path: str):
        self.messages: List[Message] = []
        self.query = ""

        # self.max_iterations = 5
        self.max_iterations = 2
        self.current_iteration = 0

        self.template = self.load_template()

        self.output_trace_path = output_trace_path

        self.llm_client = LLMClient()

    def load_template(self) -> str:
        return PROMPT

    def construct_player_stats_summary(self, player_stats) -> str:
        recent_games = player_stats
        total_games = len(recent_games)

        # Columns to include in averages
        stat_cols = [
            'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK',
            'FGM', 'FGA', 'FG_PCT',
            'FG3M', 'FG3A', 'FG3_PCT',
            'FTM', 'FTA', 'FT_PCT',
            'TOV', 'PF', 'PLUS_MINUS'
        ]

        # Ensure columns are numeric
        recent_games[stat_cols] = recent_games[stat_cols].astype(float)

        # Calculate averages
        avg_stats = recent_games[stat_cols].mean()

        # Build average summary
        summary = (
            f"        *Averages over last {total_games} games this season:*\n"
            f"        - MIN: {avg_stats['MIN']:.1f}, PTS: {avg_stats['PTS']:.1f}, REB: {avg_stats['REB']:.1f}, "
            f"AST: {avg_stats['AST']:.1f}, STL: {avg_stats['STL']:.1f}, BLK: {avg_stats['BLK']:.1f}\n"
            f"        - FG: {avg_stats['FGM']:.1f}/{avg_stats['FGA']:.1f} ({avg_stats['FG_PCT']*100:.1f}%), "
            f"3P: {avg_stats['FG3M']:.1f}/{avg_stats['FG3A']:.1f} ({avg_stats['FG3_PCT']*100:.1f}%), "
            f"FT: {avg_stats['FTM']:.1f}/{avg_stats['FTA']:.1f} ({avg_stats['FT_PCT']*100:.1f}%)\n"
            f"        - TOV: {avg_stats['TOV']:.1f}, PF: {avg_stats['PF']:.1f}, +/-: {avg_stats['PLUS_MINUS']:.1f}\n\n"
        )

        # Game-by-game stats
        summary += "        *Game-by-game stats this season:*\n"
        for _, row in recent_games.iterrows():
            summary += (
                f"        - {row['GAME_DATE']} vs {row['MATCHUP']}: "
                f"{row['PTS']} pts, {row['REB']} reb, {row['AST']} ast, "
                f"{row['STL']} stl, {row['BLK']} blk, "
                f"FG {row['FGM']}/{row['FGA']} ({row['FG_PCT']*100:.1f}%), "
                f"3P {row['FG3M']}/{row['FG3A']} ({row['FG3_PCT']*100:.1f}%), "
                f"FT {row['FTM']}/{row['FTA']} ({row['FT_PCT']*100:.1f}%), "
                f"{row['TOV']} TO, {row['PF']} PF, {row['PLUS_MINUS']} +/- in {row['MIN']} mins\n"
            )

        return summary


    def construct_game_details(self, state: GlobalState) -> str:
        game_details = ""
        game_details += """
---
## Game Info:"""
        if state.game_details is not None:
            odds_game_id = state.game_details.game_info.odds_game_id

            game_details += f"""
    - Home Team: {state.game_details.home_team_info.odds_team_name}
    - Away Team: {state.game_details.away_team_info.odds_team_name}
"""
            player_names_with_stats = []
            if len(state.game_details.players_info):
                game_details += f"""
## Recent Player Stats:
"""
                for player_info in state.game_details.players_info:
                    player_name = player_info.odds_player_name
                    player_id = player_info.nba_player_id

                    if player_id in state.player_stats:
                        player_names_with_stats.append(player_name)
                        player_stats = state.player_stats.get(player_id)
                        game_details += f"    - Player Name: {player_name}\n"
                        game_details += f"{self.construct_player_stats_summary(player_stats)}\n"

            if len(state.upcoming_bets):
                game_details += """
---
## Betting Odds:
"""

                if odds_game_id in state.upcoming_bets:
                    upcoming_bets = state.upcoming_bets.get(odds_game_id)
                    all_players = upcoming_bets.get_all_player_names()
                    for odds_player_name in all_players:
                        if odds_player_name in player_names_with_stats:
                            player_bets = upcoming_bets.get_player_market(odds_player_name)
                            game_details += f"    - Player Name: {odds_player_name}\n"

                            for bet_market, bets in player_bets.items():
                                game_details += f"        - {bet_market.upper()}\n"
                                for bet in bets:
                                    if bet.price >= 1.01:
                                        game_details += f"            - {bet.name}" + " " + f"{bet.point}" + " " + f"{decimal_to_american_odds(bet.price)}" + "\n"

        return game_details

    def ask_llm(self, prompt: str) -> str:
        contents = [Message(role='user', content=prompt)]
        response = self.llm_client.get_response(contents)

        return str(response) if response is not None else "No response from LLM"

    def execute(self, state: GlobalState) -> GlobalState:
        self.query = state.user_query
        self.game_details = self.construct_game_details(state)

        self.trace(role="user", content=self.query)
        
        self.think(state)
        
        return state

    def think(self, state: GlobalState) -> None:
        self.current_iteration += 1

        logger.info(f"Starting iteration {self.current_iteration}")
        write_to_file(path=self.output_trace_path, content=f"\n{'='*50}\nIteration {self.current_iteration}\n{'='*50}\n")

        if self.current_iteration > self.max_iterations:
            logger.warning("Reached maximum iterations. Stopping.")
            return

        prompt = self.template.format(
            query=self.query,
            history=self.get_history(),
            game_details=self.game_details
        )

        response = self.ask_llm(prompt)
        logger.info(f"Thinking => {response}")
        self.trace("assistant", f"Thought: {response}")
        
        self.decide(response, state)

    def decide(self, response: str, state: GlobalState) -> None:
        try:
            cleaned_response = response.strip().strip('`').strip()
            if cleaned_response.startswith('json'):
                cleaned_response = cleaned_response[4:].strip()
            
            parsed_response = json.loads(cleaned_response, strict=False)

            if "answer" in parsed_response:
                self.trace("assistant", f"Final Answer: {parsed_response['answer']}")

                state.final_answer = parsed_response['answer']
            else:
                raise ValueError("Invalid response format")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {response}. Error: {str(e)}")
            self.trace("assistant", f"I encountered an error in processing. Error: {str(e)}. Let me try again.")

            self.think(state)
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            self.trace("assistant", f"I encountered an unexpected error. Error: {str(e)}. Let me try a different approach.")

            self.think(state)

    def get_history(self) -> str:
        if len(self.messages) > 0:
            return "Previous reasoning steps and observations: " + "\n".join([f"{message.role}: {message.content}" for message in self.messages])
        return ""

    def trace(self, role: str, content: str) -> None:
        write_to_file(path=self.output_trace_path, content=f"{role}: {content}\n")
