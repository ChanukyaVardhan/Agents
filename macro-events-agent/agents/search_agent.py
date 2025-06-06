from state import GlobalState, SearchQueryResult, Event
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from langchain_community.tools import DuckDuckGoSearchResults
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
You are a specialized macro economic filtering AI agent within a broader ecosystem of intelligent agents that help prepare the user for the upcoming macro economic event.

# Event Information
- **Event Name**: {event_name}
- **Event Date**: {event_date}

# Search Results
{search_results}

Your goal is to select the **top 5 most relevant URLs** that likely contain valuable information related to the macroeconomic event above, and providing the reason for our choice.

# Instructions:
- Is the article about this specific event?
- Does it include forecasts, analysis, or past insights?
- Is it from a credible source? Give higher preference to official sites.

Return only the **top 5 URLs** in JSON format. Make sure it is a valid JSON format. Your output should only contain the json response without any further text:
```json
{{
  "top_urls": ["url1", "url2", "url3", "url4", "url5"],
  "reason": "Explanation of why you chose these urls"
}}
"""

class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender (e.g., 'user', 'assistant').")
    content: str = Field(..., description="The content of the message.")


class SearchAgent:
    def __init__(self, output_trace_path: str):
        self.output_trace_path = output_trace_path
        self.search = DuckDuckGoSearchResults(output_format="json", max_results=10) # Reduced from 20

        if not FIRE_CRAWL_API:
            logger.error("FIRE_CRAWL_API key not found in environment variables.")
            raise ValueError("FIRE_CRAWL_API key is required for SearchAgent.")
        
        self.firecrawl_app = FirecrawlApp(api_key=FIRE_CRAWL_API)
        self.llm_client = LLMClient()

    def trace(self, role: str, content: str) -> None:
        write_to_file(path=self.output_trace_path, content=f"{role}: {content}\n")

    def ask_llm(self, prompt: str) -> Optional[str]:
        self.trace("user", prompt)

        contents = [Message(role='user', content=prompt)]
        response = self.llm_client.get_response(contents)

        return response

    def build_prompt(self, state: GlobalState) -> str:
        event_name = state.current_event.name
        event_date = state.current_event.date

        # Flatten and pretty-print search results
        search_results = ""
        for search_result in state.current_event.search_query_results:
            search_results += f"  - Title: {search_result.title}\n"
            search_results += f"    - Link: {search_result.link}\n"
            search_results += f"    - Snippet: {search_result.snippet}\n"

        return PROMPT.format(
            event_name=event_name,
            event_date=event_date,
            search_results=search_results
        )

    def parse_top_urls(self, response: str) -> List[str]:
        try:
            cleaned = response.strip().strip('`').strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[len("json"):].strip()

            parsed = json.loads(cleaned, strict=False)
            return parsed.get("top_urls", [])
        except Exception as e:
            # TODO: raise error here
            logger.error(f"SearchAgent: Failed to parse response: {e}.")
            logger.error(f"SearchAgent: Not returning any urls for now.")
            return []

    def execute_search(self, state: GlobalState) -> GlobalState:
        # TODO: Defaulting to forecast query for now
        search_str = f"{state.current_event.name} forecast"
        
        logger.info(f"SearchAgent: Executing search query for - {search_str}")
        try:
            search_query_results_json = json.loads(self.search.invoke(search_str), strict=False)
            search_query_results = [
                SearchQueryResult(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    snippet=item.get("snippet", "")
                )
                for item in search_query_results_json
            ]

            logger.info(f"SearchAgent: Search query results - {search_query_results}")

            state.current_event.search_query_results = search_query_results
        except Exception as e:
            logger.error(f"SearchAgent: Failed to execute search: {e}.")

        return state

    def execute(self, state: GlobalState) -> GlobalState:
        logger.info("SearchAgent: Starting execution.")

        if not state.current_event or not state.current_event.name:
            logger.error("SearchAgent: Cannot execute, current_event is not set or has no name.")
            # TODO: BETTER TO STOP HERE
            return state

        self.execute_search(state)

        # Check if search results were found before building prompt
        if not state.current_event.search_query_results:
            logger.warning("SearchAgent: No search results found for the current event.")
            # TODO: BETTER TO STOP HERE
            return state

        prompt = self.build_prompt(state)
        response = self.ask_llm(prompt)
        if not response:
            logger.warning("SearchAgent: No response from LLM to select top urls.")
            # TODO: BETTER TO STOP HERE
            return state

        logger.info(f"SearchAgent: LLM response: {response}")

        self.trace("assistant", response)

        # TODO: Handle ordering of the urls.
        # TODO: Check the loop is doing only for 5 urls.
        top_urls = self.parse_top_urls(response)
        if len(top_urls) == 0:
            logger.warning("SearchAgent: No top URLs parsed from LLM response. No content will be scraped.")
            # TODO: BETTER TO STOP HERE
            return state

        for search_result in state.current_event.search_query_results:
            if search_result.link in top_urls:
                search_result.is_top_result = True

                try:
                    logger.info(f"SearchAgent: Scraping the url - {search_result.link}")
                    scrape_result = self.firecrawl_app.scrape_url(
                        url=search_result.link,
                        formats=["markdown"],
                        only_main_content= True
                    )
                    search_result.scraped_content = scrape_result
                    logger.info(f"\n\n{scrape_result}\n\n")
                except Exception as e:
                    logger.error(f"SearchAgent: Failed to scrape {search_result.link}: {e}.")
                    search_result.scraped_content = "Could not scrape any content from this page."

        return state
