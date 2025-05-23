from langgraph.graph import StateGraph, END
from agents.events_agent import EventsAgent
from agents.search_agent import SearchAgent
from agents.summarizer_agent import SummarizerAgent
from state import GlobalState, Event, SearchQueryResult
from calendar_tools import GoogleCalendar
from datetime import datetime, timedelta
from utils import logger
import pprint
import sys


OUTPUT_PATH = "output/output.txt"
CALENDAR_API_TOKEN_PATH = "api_keys/calendarapi_token.json"
CALENDAR_API_CREDENTIALS_PATH = "api_keys/calendarapi_credentials.json"

def events_node(state: GlobalState) -> GlobalState:
    result = events_agent.execute(state)
    return result

def search_node(state: GlobalState) -> GlobalState:
    result = search_agent.execute(state)
    return result

def summarizer_node(state: GlobalState) -> GlobalState:
    result = summarizer_agent.execute(state)
    return result


if __name__ == "__main__":
    logger.info("Macro Events Agent starting...")

    try:
        logger.info("Initializing GoogleCalendar service...")
        calendar_service = GoogleCalendar(
            token_path=CALENDAR_API_TOKEN_PATH,
            credentials_path=CALENDAR_API_CREDENTIALS_PATH
        )
        logger.info("GoogleCalendar service initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize GoogleCalendar service: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Initializing agents...")
    try:
        events_agent = EventsAgent(OUTPUT_PATH)
        search_agent = SearchAgent(OUTPUT_PATH)
        summarizer_agent = SummarizerAgent(OUTPUT_PATH)
        logger.info("Agents initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}", exc_info=True)
        sys.exit(1)

    def events_node(state: GlobalState) -> GlobalState:
        result = events_agent.execute(state)
        return result

    def search_node(state: GlobalState) -> GlobalState:
        result = search_agent.execute(state)
        return result

    def summarizer_node(state: GlobalState) -> GlobalState:
        result = summarizer_agent.execute(state)
        return result

    # --- Build Graph ---
    logger.info("Building LangGraph state machine...")
    builder = StateGraph(GlobalState)
    builder.add_node("events_agent", events_node)
    builder.add_node("search_agent", search_node)
    builder.add_node("summarizer_agent", summarizer_node)

    builder.set_entry_point("events_agent")
    builder.add_edge("events_agent", "search_agent")
    builder.add_edge("search_agent", "summarizer_agent")
    builder.add_edge("summarizer_agent", END)

    graph = builder.compile()
    logger.info("LangGraph state machine built successfully.")


    # --- Main Workflow ---
    start_time = datetime.utcnow() + timedelta(days=-7)
    end_time = start_time + timedelta(days=7)
    events_in_calendar = calendar_service.get_events(start_time, end_time)

    initial_state = GlobalState()
    for event in events_in_calendar:
        # TODO: Handle failures here?
        initial_state.events_in_calendar.append(
            Event(
                name=event["summary"],
                date=event["start"]
            )
        )
    final_state = graph.invoke(initial_state)

    current_event = final_state["current_event"]
    if current_event:
        new_event = calendar_service.create_event(
            current_event.name,
            current_event.summary if current_event.summary is not None else "Meeting prep not available for this event.",
            current_event.date,
            add_7_am_notifications=True
        )
        pprint.pprint(new_event)

    logger.info("Macro Events Agent finished.")
