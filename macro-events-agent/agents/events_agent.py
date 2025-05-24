from state import GlobalState, SearchQueryResult, Event
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from llm import LLMClient
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from utils import write_to_file
from utils import logger
import json
import os

load_dotenv()

FIRE_CRAWL_API = os.getenv("FIRE_CRAWL_API")

PROMPT = """
You are a specialized macro economic AI agent within a broader ecosystem of intelligent agents that help prepare the user for the upcoming macro economic event.
Your goal is to select the most important macroeconomic events in the United States from the above upcoming events that were scraped from a webpage of an economic calendar, and not already in my google calendar.

# Instructions:
- DO NOT PICK EVENTS BEFORE TODAY.
- Today's date is {today_date}.
- ONLY PICK UPCOMING EVENTS IN THE NEXT 7 DAYS AFTER TODAY.
- DO NOT PICK EVENTS BEFORE TODAY.
- DO NOT PICK EVENTS ALREADY IN MY CALENDAR.
- You can assume all the event times in the scraped webpage are NYC timezone times. THERE IS NO NEED TO SPECIFY THE TIMEZONE IN THE RESPONSE.
- Select events that have the most impact on markets. Do not limit yourself in the number of events to select, but make sure they are the most important.
- If there are multiple indicators listed that are part of the same report, create only one event for them.

# Events in my calendar:
{google_calendar_events}

# Upcoming Events:
{upcoming_events}

Return only the **most important upcoming events** in JSON format. Make sure it is a valid JSON format. Your output should only contain the json response without any further text:
```json
{{
  [
    {{
      "event_name": "Name of the event/report",
      "event_date": "Date and time of the event in the YYYY-MM-DDTHH:mm:ss format",
      "reason": "Why is this event important?"
    }}
  ]
}}
"""

class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender (e.g., 'user', 'assistant').")
    content: str = Field(..., description="The content of the message.")


class EventsAgent:
    def __init__(self, output_trace_path: str):
        self.output_trace_path = output_trace_path

        if not FIRE_CRAWL_API:
            logger.error("FIRE_CRAWL_API key not found in environment variables.")
            raise ValueError("FIRE_CRAWL_API key is required for EventsAgent.")

        self.firecrawl_app = FirecrawlApp(api_key=FIRE_CRAWL_API)
        self.llm_client: LLMClient = LLMClient()

    def trace(self, role: str, content: str) -> None:
        write_to_file(path=self.output_trace_path, content=f"{role}: {content}\n")

    def ask_llm(self, prompt: str) -> Optional[str]:
        self.trace("user", prompt)

        contents = [Message(role='user', content=prompt)]
        response = self.llm_client.get_response(contents)

        return response

    def build_prompt(self, state: GlobalState) -> str:
        # Format calendar events with the new format
        if state.events_in_calendar:
            calendar_events_formatted = "\n".join([
                f"\n- **Event Name**: {event.name}\n- **Event Date**: {event.date}\n"
                for event in state.events_in_calendar
            ])
        else:
            calendar_events_formatted = "No events in the calendar."


        # TODO: We can use multiple urls and scrape multiple of them.
        market_watch_us_calendar_url = "https://www.marketwatch.com/economy-politics/calendar"
        try:
            scrape_result = self.firecrawl_app.scrape_url(
                url=market_watch_us_calendar_url,
                formats=["markdown"],
                only_main_content= True
            )
            logger.info(f"\n\n{scrape_result}\n\n")
        except Exception as e:
            logger.error(f"EventsAgent: Failed to scrape {market_watch_us_calendar_url}: {e}", exc_info=True)
            raise

        return PROMPT.format(
            google_calendar_events=calendar_events_formatted,
            upcoming_events=scrape_result,
            today_date = datetime.now().strftime("%Y-%m-%d")
        )

    def parse_upcoming_events(self, response: str) -> List[Dict[str, str]]:
        try:
            cleaned = response.strip().strip('`').strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[len("json"):].strip()
            parsed = json.loads(cleaned, strict=False)
            return parsed
        except Exception as e:
            # TODO: raise error here
            logger.error(f"EventsAgent: Failed to parse response: {e}.")
            logger.error(f"EventsAgent: Not returning upcoming events now.")
            return []

    def execute(self, state: GlobalState) -> GlobalState:
        logger.info("EventsAgent: Starting execution.")

        prompt = self.build_prompt(state)
        response = self.ask_llm(prompt)
        if not response:
            logger.warning("SearchAgent: No response from LLM to pick important upcoming macro events.")
            # TODO: BETTER TO STOP HERE
            return state

        logger.info(f"EventsAgent: LLM response: {response}")

        self.trace("assistant", response)

        upcoming_events = self.parse_upcoming_events(response)
        state.upcoming_events = [
            Event(
                name=upcoming_event["event_name"],
                # TODO: Fix the timestamp here
                date=upcoming_event["event_date"].replace("-04:00", "").replace("-05:00", "")
            ) for upcoming_event in upcoming_events
        ]

        if len(state.upcoming_events) != 0:
            state.current_event_index = 0
        else:
            logger.warning("EventsAgent: No upcoming events were added to the state.")
            state.current_event_index = -1

        return state
