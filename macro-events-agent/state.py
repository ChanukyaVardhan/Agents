from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd
import pickle

@dataclass
class SearchQueryResult:
	title: str
	link: str
	snippet: str
	scraped_content: Optional[str] = None
	is_top_result: bool = False


@dataclass
class Event:
	name: str
	# TODO: Fix the date to use datetime instead of string
	date: str
	summary: Optional[str] = None

	search_query_results: List[SearchQueryResult] = field(default_factory=list)


@dataclass
class GlobalState:
	upcoming_events: List[Event] = field(default_factory=list)
	current_event: Optional[Event] = None
	current_event_index: int = -1
	events_in_calendar: List[Event] = field(default_factory=list)
