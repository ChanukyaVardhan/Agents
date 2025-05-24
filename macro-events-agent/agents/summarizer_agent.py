from state import GlobalState
from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchResults
from llm import LLMClient
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from utils import write_to_file
from utils import logger
import json
import os


PROMPT = """
You are a specialized research assistant AI agent within a broader ecosystem of intelligent agents that help prepare the user for the upcoming macro economic event.

# Event Details
- **Event Name**: {event_name}
- **Event Date**: {event_date}

Your goal is to generate a concise but comprehensive preview/summary for the upcoming macro economic event, and relevant ETFs that would see price changes because of this event.
You are given results from web search for this event along with snippets and scraped content from these links.

{search_summary}

# Instructions
- For numbers, use only data scraped from the web search content.
- If you don't have enough data about the forecast or historical data, don't make up numbers.
- Since the content is scraped, you might find irrelevant and unstructured content. Pick only relevant information from that.
- You can use your own knowledge when explaining details about importance of the event.
- For references, list down all the urls that you referred the content from.
- Provide citations for the content generated.

Your output must be a JSON object with the following structure. Make sure it is a valid JSON format. Your output should only contain the json response without any further text:
```json
{{
  "event_details": "A broad title for the event along with date and time.",
  "forecast": "Summarize current market expectations (monthly and annual changes if relevant), including consensus figures and expert/analyst projections. Mention key trends or market sentiment leading into the event.",
  "history": "Briefly outline what happened in the previous month's report, and how markets or analysts interpreted that. Mention any notable surprises or shifts in underlying data. Include relevant YoY and MoM comparisons. Quote reliable sources (with attribution and embedded URLs).",
  "significance": "Explain why this event matters for markets. What does the data typically indicate? What could a surprise in either direction (stronger or weaker data) imply for equities, yields, Fed policy, or inflation expectations? Include any sectoral or macroeconomic implications.",
  "latest_news": "Summarize what the most recent articles (provided) are reporting or predicting. Are there any new factors at play (e.g., policy changes, geopolitical tensions, weather events, etc.) that may affect this release or its interpretation?",
  "etfs": "Explain the ETFs I can trade that have high impact for this event, along with how to do execute the trade based on the direction of the results",
  "references": ["url1", "url2", ...]
}}
"""

class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender (e.g., 'user', 'assistant').")
    content: str = Field(..., description="The content of the message.")


class SummarizerAgent:
    def __init__(self, output_trace_path: str):
        self.template = self.load_template()
        self.output_trace_path = output_trace_path
        self.llm_client = LLMClient()

    def load_template(self) -> str:
        return PROMPT

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

        search_summary = "# Articles\n"
        counter = 0
        for scraped_result in state.current_event.search_query_results:
            if scraped_result.is_top_result:
                search_summary += f"## Article {counter+1}:\n"
                search_summary += f"- *Title*: {scraped_result.title}\n"
                search_summary += f"- *Link*: {scraped_result.link}\n"
                search_summary += f"- *Snippet*: {scraped_result.snippet}\n"
                if scraped_result.scraped_content is not None:
                    search_summary += f"- *Scraped Content*: {scraped_result.scraped_content}\n"
                else:
                    search_summary += f"- *Scraped Content*: Could not scrape any content from this page.\n"
                search_summary += "\n\n"

                counter += 1

        return self.template.format(
            event_name=event_name,
            event_date=event_date,
            search_summary=search_summary
        )

    def parse_summary(self, response: str) -> Dict[str, str]:
        summary = {}
        try:
            cleaned_response = response.strip().strip('`').strip()
            if cleaned_response.startswith('json'):
                cleaned_response = cleaned_response[len("json"):].strip()

            parsed_response = json.loads(cleaned_response, strict=False)
            summary = parsed_response

            return summary
        except Exception as e:
            logger.error(f"SummarizerAgent: Failed to parse response: {e}.")
            return {"error": e}

    def format_summary_for_calendar(self, summary: Dict[str, str]) -> str:
        if "error" in summary:
            return "Error generating summary."

        parts: List[str] = []
        def append_if_present(key: str, title: str):
            value = summary.get(key)
            if value:
                if isinstance(value, list): # For references
                    if value: # If list is not empty
                        parts.append(f"**{title}:**\n" + "\n".join(f"- {item}" for item in value))
                else: # For string values
                     parts.append(f"**{title}:**\n{value}")
            parts.append("\n")

        append_if_present("event_details", "Event Details")
        append_if_present("forecast", "Forecast")
        append_if_present("history", "Previous Report Recap")
        append_if_present("significance", "Why This Matters")
        append_if_present("latest_news", "Latest Developments")
        append_if_present("etfs", "ETFs to Watch")
        append_if_present("references", "References")

        return "\n".join(parts).strip()

    def execute(self, state: GlobalState) -> GlobalState:
        logger.info("SummarizerAgent: Starting execution.")

        if not state.current_event or not state.current_event.name:
            logger.error("SummarizerAgent: Cannot execute, current_event is not set or has no name.")
            # TODO: BETTER TO STOP HERE
            return state

        prompt = self.build_prompt(state)
        response = self.ask_llm(prompt)
        if not response:
            logger.warning("SummarizerAgent: No response from LLM for summary generation. Setting error summary.")
            state.current_event.summary = "Error: No response from LLM during summary generation."
            return state

        logger.info(f"SummarizerAgent: LLM response: {response}")

        self.trace("assistant", response)

        parsed_response = self.parse_summary(response)
        state.current_event.summary = self.format_summary_for_calendar(parsed_response)
        logger.info(f"\n{state.current_event.summary}\n")

        return state
