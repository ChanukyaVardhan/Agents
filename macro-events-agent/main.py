from langgraph.graph import StateGraph, END
from agents.events_agent import EventsAgent
from agents.search_agent import SearchAgent
from agents.summarizer_agent import SummarizerAgent
from state import GlobalState, Event, SearchQueryResult
from calendar_tools import authenticate_google_calendar, get_events, create_event
from datetime import datetime, timedelta
import pprint


OUTPUT_PATH = "output/output.txt"
CALENDAR_API_TOKEN_PATH = "api_keys/calendarapi_token.json"
CALENDAR_API_CREDENTIALS_PATH = "api_keys/calendarapi_credentials.json"

calendar_service = authenticate_google_calendar(CALENDAR_API_TOKEN_PATH, CALENDAR_API_CREDENTIALS_PATH)

events_agent = EventsAgent(OUTPUT_PATH)
searh_agent = SearchAgent(OUTPUT_PATH)
summarizer_agent = SummarizerAgent(OUTPUT_PATH)


def events_node(state: GlobalState) -> GlobalState:
    result = events_agent.execute(state)
    return result

def search_node(state: GlobalState) -> GlobalState:
    result = searh_agent.execute(state)
    return result

def summarizer_node(state: GlobalState) -> GlobalState:
    result = summarizer_agent.execute(state)
    return result

builder = StateGraph(GlobalState)

builder.add_node("events_agent", events_node)
builder.add_node("search_agent", search_node)
builder.add_node("summarizer_agent", summarizer_node)

builder.set_entry_point("events_agent")
builder.add_edge("events_agent", "search_agent")
builder.add_edge("search_agent", "summarizer_agent")
builder.add_edge("summarizer_agent", END)

graph = builder.compile()

if __name__ == "__main__":
    start_time = datetime.utcnow() + timedelta(days=-7)
    end_time = start_time + timedelta(days=7)
    events_in_calendar = get_events(calendar_service, start_time, end_time)

    initial_state = GlobalState()
    for event in events_in_calendar:
        initial_state.events_in_calendar.append(
            Event(
                name=event["summary"],
                date=event["start"]
            )
        )
    final_state = graph.invoke(initial_state)

    current_event = final_state["current_event"]
    if current_event:
        new_event = create_event(
            calendar_service,
            current_event.name,
            current_event.summary if current_event.summary is not None else "Meeting prep not available for this event.",
            current_event.date,
            add_7_am_notifications=True
        )
        pprint.pprint(new_event)
