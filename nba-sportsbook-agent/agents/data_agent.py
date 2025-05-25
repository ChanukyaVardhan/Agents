from llm import LLMClient
from pydantic import BaseModel, Field
from state import GlobalState
from tools import Tool
from typing import Callable, Dict, List, Optional
from utils import logger, write_to_file
import json
import tools as t


PROMPT = """
You are a Data Agent in a multi-agent NBA sportsbook system.

Your role is to examine the user's query and determine what data is required to fulfill it. You have access to a shared state that may already contain some data. Your task is to identify any missing data and use the appropriate tools to load only the missing parts.

Query: {query}

Current known data in memory (state): {current_state}

Previous reasoning steps and observations: {history}

Available tools: {tools}

Instructions:
1. Determine data required to fulfill the query.
2. Compare that with the current state to identify missing data.
3. Use tools to load only the missing data.
4. Tools always take keyword arguments or no arguments. Structure of the inputs is already provided in the available tools. Respect the input format strictly, don't add comments in the arguments.
5. If all required data is already available, pass control to the next agent.

Respond only in this JSON format:

If you need to use a tool:
{{
    "thought": "What data is missing and why this tool is needed.",
    "action": {{
        "name": "Tool name (e.g., load_upcoming_nba_games_and_bets)",
        "reason": "Why this tool is necessary now",
        "input": "Explicit input the tool needs, if any"
    }}
}}

If no more data is needed:
{{
    "thought": "Why the data is now complete",
    "answer": "Data is ready. Pass to the next agent."
}}

Guidelines:
- Never provide final analysis or betting insights.
- Only focus on determining and acquiring required data.
- Avoid redundant tool calls for already available data.
- Make decisions solely based on the current query and what’s missing in state.
"""


class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender.")
    content: str = Field(..., description="The content of the message.")


class DataAgent:

    def __init__(self, output_trace_path: str):
        self.tools: Dict[str, Tool]
        self.messages: List[Message] = []
        self.query = ""

        self.max_iterations = 5
        self.current_iteration = 0

        self.load_tools()

        self.template = self.load_template()
        self.tool_descriptions = self.load_tool_descriptions()

        self.output_trace_path = output_trace_path

        self.llm_client = LLMClient()

    def load_tools(self):
        self.tools: Dict[str, Tool] = {
            "LOAD_UPCOMING_NBA_GAMES_AND_BETS": Tool(
                name="load_upcoming_nba_games_and_bets",
                func=t.load_upcoming_nba_games_and_bets,
                tool_description="Loads all upcoming NBA games with their team IDs, names, and player IDs, names; and sportsbook bets with bet event id, team names, player names and bet markets.",
                tool_inputs={},  # no inputs
                tool_outputs="(Dict[nba_game_id, Dict[NBATeamInfo, List[NBAPlayerInfo]]], Dict[bet_event_id, BetEvent])"
            ),
            "LOAD_PLAYERS_STATS": Tool(
                name="load_players_stats",
                func=t.load_players_stats,
                tool_description="Loads NBA players stats for the given list of player IDs. Note the player ids are the ids from NBA website and not names from the Odds API",
                tool_inputs={
                    "player_ids": ["player_id_1", "player_id_2", "player_id_n"]
                },
                tool_outputs="Dict[str, PlayerStats]"  # TODO: Check this part
            )
        }

    def load_template(self) -> str:
        return PROMPT

    def load_tool_descriptions(self) -> str:
        return "\n".join([tool.describe() for tool in self.tools.values()])

    def ask_llm(self, prompt: str) -> str:
        contents = [Message(role='user', content=prompt)]
        response = self.llm_client.get_response(contents)

        return str(response) if response is not None else "No response from LLM"

    def think(self, state: GlobalState) -> None:
        self.current_iteration += 1

        logger.info(f"Starting iteration {self.current_iteration}")
        write_to_file(path=self.output_trace_path, content=f"\n{'='*50}\nIteration {self.current_iteration}\n{'='*50}\n")

        if self.current_iteration > self.max_iterations:
            logger.warning("Reached maximum iterations. Stopping.")
            return

        prompt = self.template.format(
            query=self.query,
            current_state=state.summarize_state_for_data_agent(),
            history=self.get_history(),
            tools=self.tool_descriptions
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
            
            if "action" in parsed_response:
                action = parsed_response["action"]
                tool_name = action["name"].upper()
                self.trace("assistant", f"Action: Using {tool_name} tool")

                action_input = action.get("input", None)
                if (action_input is None or action_input == {}):
                    self.act(tool_name, None, state)
                else:
                    self.act(tool_name, action_input, state)
            elif "answer" in parsed_response:
                self.trace("assistant", f"Final Answer: {parsed_response['answer']}")

                state.required_data_loaded = True
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

    def act(self, tool_name: str, query: Dict, state: GlobalState) -> None:
        tool = self.tools.get(tool_name)
        if tool:
            result = tool.use(query)
            
            if tool_name == "LOAD_UPCOMING_NBA_GAMES_AND_BETS" and isinstance(result, tuple):
                state.upcoming_games = result[0]
                state.upcoming_bets = result[1]
                result = "Successfully loaded upcoming NBA games along with the bets into state."
            elif tool_name == "LOAD_PLAYERS_STATS" and isinstance(result, dict):
                for key, df in result.items():
                    state.player_stats[key] = df
                result = "Successfully loaded player stats for " + ",".join(result.keys())
            
            observation = f"Observation from {tool_name}: {result}"
            self.trace("system", observation)
            self.messages.append(Message(role="system", content=observation))  # Add observation to message history

            self.think(state)
        else:
            logger.error(f"No tool registered for choice: {tool_name}")
            self.trace("system", f"Error: Tool {tool_name} not found")
            # TODO: SHOULDN'T THIS MESSAGE ALSO BE ADDED??

            self.think(state)

    def get_history(self) -> str:
        return "\n".join([f"{message.role}: {message.content}" for message in self.messages])

    def trace(self, role: str, content: str) -> None:
        if role != "system":
            self.messages.append(Message(role=role, content=content))
        write_to_file(path=self.output_trace_path, content=f"{role}: {content}\n")

    def execute(self, state: GlobalState) -> GlobalState:
        logger.info("DataAgent: Starting execution.")

        self.query = state.user_query
        self.trace(role="user", content=self.query)
        
        self.think(state)
        
        return state
