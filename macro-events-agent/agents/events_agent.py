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
- Select events that have the most impact on markets. Do not limit yourself in the number of events to select, make sure they are important.
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
            # scrape_result = self.firecrawl_app.scrape_url(
            #     url=market_watch_us_calendar_url,
            #     formats=["markdown"],
            #     only_main_content= True
            # )
            # scrape_result = """url=None markdown='[Economy & Politics](https://www.marketwatch.com/economy-politics?mod=u.s.-economic-calendar)\n\n- [The Fed](https://www.marketwatch.com/economy-politics/federal-reserve?mod=u.s.-economic-calendar)\n- [U.S. Economic Calendar](https://www.marketwatch.com/economy-politics/calendars/economic?mod=u.s.-economic-calendar)\n- [Economic Report](https://www.marketwatch.com/column/economic-report?mod=u.s.-economic-calendar)\n- [Inflation](https://www.marketwatch.com/economy-politics/inflation?mod=u.s.-economic-calendar)\n- [Washington Watch](https://www.marketwatch.com/column/washington-watch?mod=u.s.-economic-calendar)\n\n1. [Home](https://www.marketwatch.com/?mod=u.s.-economic-calendar)\n2. [Economy & Politics](https://www.marketwatch.com/economy-politics?mod=u.s.-economic-calendar)\n3. U.S. Economic Calendar\n\n# This Week\'s Major U.S. Economic Reports & Fed Speakers\n\n| Time (ET) | Report | Period | Actual | Median Forecast | Previous |\n| --- | --- | --- | --- | --- | --- |\n| **MONDAY, MAY 19** |  |  |  |  |  |\n| 8:45 am | New York Fed President John Williams speech |  |  |  |  |\n| 8:45 am | [Fed Vice Chair Philip Jefferson speech](https://www.federalreserve.gov/newsevents/speech/jefferson20250519a.htm) |  |  |  |  |\n| 10:00 am | [U.S. leading economic indicators](https://www.conference-board.org/topics/us-leading-indicators) | April | -1.0% | -0.9% | -0.8% |\n| **TUESDAY, MAY 20** |  |  |  |  |  |\n| 9:00 am | [Richmond Fed President Tom Barkin speech](https://www.richmondfed.org/press_room/speeches/thomas_i_barkin/2025/barkin_speech_20250520) |  |  |  |  |\n| 9:30 am | [Boston Fed President Susan Collins participates in Fed Listens event](https://www.bostonfed.org/news-and-events/speeches/2025/fedlistens-remarks.aspx) |  |  |  |  |\n| 1:00 pm | [St. Louis Fed President Alberto Musalem speech](https://www.stlouisfed.org/from-the-president/remarks/2025/economic-conditions-and-monetary-policy-remarks-economic-club-of-minnesota) |  |  |  |  |\n| 7:00 pm | [San Francisco Fed President Mary Daly and Cleveland Fed President Beth Hammack in panel discussion](https://www.atlantafed.org/news/conferences-and-events/conferences/2025/05/18/financial-markets-conference/) |  |  |  |  |\n| **WEDNESDAY, MAY 21** |  |  |  |  |  |\n| 7:00 pm | [Richmond Fed President Tom Barkin and Fed Governor Michelle Bowman take part in Fed Listens event](https://www.richmondfed.org/conferences_and_events/2025/20250521_fed_listens) |  |  |  |  |\n| **THURSDAY, MAY 22** |  |  |  |  |  |\n| 8:30 am | [Initial jobless claims](https://www.marketwatch.com/story/jobless-claims-point-to-steady-job-growth-in-may-69e8aa87?mod=home_ln) | May 17 | 227,000 | 230,000 | 229,000 |\n| 9:45 am | [S&P flash U.S. services PMI](https://www.marketwatch.com/story/u-s-economy-improves-in-may-after-slump-last-month-s-p-pmi-surveys-show-2c17690f?mod=home_ln) | May | 52.3 | 50.6 | 50.8 |\n| 9:45 am | S&P flash U.S. manufacturing PMI | May | 52.3 | 49.8 | 50.2 |\n| 10:00 am | [Existing home sales](https://www.marketwatch.com/story/buyers-are-gaining-the-upper-hand-in-a-shifting-housing-market-everybody-wants-a-deal-c880e75f?mod=home_ln) | April | 4.0 million | 4.13 million | 4.02 million |\n| 2:00 pm | [New York Fed President John Williams speech](https://www.newyorkfed.org/newsevents/speeches/2025/wil250522) |  |  |  |  |\n| **FRIDAY, MAY 23** |  |  |  |  |  |\n| 9:35 am | Kansas City Fed President Jeff Schmid and St. Louis Fed President Alberto Musalem on panel |  |  |  |  |\n| 10:00 am | New home sales | April |  | 695,000 | 724,000 |\n| 12:00 pm | Federal Reserve Governor Lisa Cook speech |  |  |  |  |\n| **SUNDAY, MAY 25** |  |  |  |  |  |\n| 2:40 pm | Federal Reserve Chair Jerome Powell commencement address |  |  |  |  |\n\n# Next Week\'s Major U.S. Economic Reports & Fed Speakers\n\n| Time (ET) | Report | Period | Actual | Median Forecast | Previous |\n| --- | --- | --- | --- | --- | --- |\n| **MONDAY, MAY 26** |  |  |  |  |  |\n|  | None scheduled, Memorial Day holiday |  |  |  |  |\n| **TUESDAY, MAY 27** |  |  |  |  |  |\n| 8:30 am | Durable-goods orders | April |  |  | 9.2% |\n| 8:30 am | Durable-goods minus transportation | April |  |  | 0.0% |\n| 9:00 am | S&P CoreLogic Case-Shiller home price index (20 cities) | March |  |  | 4.5% |\n| 10:00 am | Consumer confidence | May |  |  | 86.0 |\n| **WEDNESDAY, MAY 28** |  |  |  |  |  |\n| 2:00 pm | Minutes of Fed\'s May FOMC meeting |  |  |  |  |\n| **THURSDAY, MAY 29** |  |  |  |  |  |\n| 8:30 am | Initial jobless claims | May 24 |  |  |  |\n| 8:30 am | GDP (First revision) | Q1 |  |  | -0.3% |\n| 10:00 am | Pending home sales | April |  | -- | 6.1% |\n| **FRIDAY, MAY 30** |  |  |  |  |  |\n| 8:30 am | Personal income | April |  |  | 0.5% |\n| 8:30 am | Personal spending | April |  |  | 0.7% |\n| 8:30 am | PCE index | April |  |  | 0.0% |\n| 8:30 am | PCE (year-over-year) |  |  |  | 2.3% |\n| 8:30 am | Core PCE index | April |  |  | 0.0% |\n| 8:30 am | Core PCE (year-over-year) |  |  |  | 2.6% |\n| 8:30 am | Advanced U.S. trade balance in goods | April |  |  | -$163.2B |\n| 8:30 am | Advanced retail inventories | April |  |  | -0.1% |\n| 8:30 am | Advanced wholesale inventories | April |  |  | 0.4% |\n| 9:45 am | Chicago Business Barometer (PMI) | May |  |  | 44.6 |\n| 10:00 am | Consumer sentiment (final) | May |  |  | 50.8 |\n\n# Last Week\'s Major U.S. Economic Reports & Fed Speakers\n\n| Time (ET) | Report | Period | Actual | Median Forecast | Previous |\n| --- | --- | --- | --- | --- | --- |\n| **MONDAY, MAY 12** |  |  |  |  |  |\n| 10:25 am | [Fed Governor Adriana Kugler speech](https://www.federalreserve.gov/newsevents/speech/kugler20250512a.htm) |  |  |  |  |\n| 2:00 pm | [Monthly U.S. federal budget](https://www.fiscal.treasury.gov/reports-statements/mts/) | April | $258B | $256B | $210B |\n| **TUESDAY, MAY 13** |  |  |  |  |  |\n| 6:00 am | [NFIB optimism index](https://www.nfib.com/news/monthly_report/sbet/) | April | 95.8 | 95.0 | 97.4 |\n| 8:30 am | [Consumer price index](https://www.marketwatch.com/story/consumer-prices-post-mild-increase-in-april-but-trade-wars-likely-to-add-to-inflation-despite-reduced-tariffs-32757558?mod=home_ln) | April |  | 0.2% | -0.1% |\n| 8:30 am | CPI year over year |  |  | 2.4% | 2.4% |\n| 8:30 am | Core CPI | April |  | 0.3% | 0.1% |\n| 8:30 am | Core CPI year over year |  |  | 2.8% | 2.8% |\n| **WEDNESDAY, MAY 14** |  |  |  |  |  |\n| 5:15 am | [Fed Governor Christopher Waller speech](https://www.federalreserve.gov/newsevents/speech/waller20250514a.htm) |  |  |  |  |\n| 9:10 am | [Fed Vice Chair Philip Jefferson speech](https://www.federalreserve.gov/newsevents/speech/jefferson20250514a.htm) |  |  |  |  |\n| 5:40 pm | San Francisco Fed President Mary Daly speech |  |  |  |  |\n| **THURSDAY, MAY 15** |  |  |  |  |  |\n| 8:30 am | [Initial jobless claims](https://www.marketwatch.com/story/jobless-claims-hold-steady-in-latest-week-continuing-to-signal-healthy-labor-market-db1f0f84?mod=home_ln) | May 10 | 229,000 | 226,000 | 229,000 |\n| 8:30 am | [U.S. retail sales](https://www.marketwatch.com/story/retail-sales-peter-out-in-april-as-tariffs-kicked-in-60dcbaf4?mod=home_ln) | April | 0.1% | 0.1% | 1.7% |\n| 8:30 am | Retail sales minus autos | April | 0.1% | 0.3% | 0.8% |\n| 8:30 am | [Producer price index](https://www.marketwatch.com/story/wholesale-inflation-shows-biggest-drop-since-2020-but-its-unlikely-to-last-f063a765?mod=economy-politics) | April | 0.5% | 0.3% | -0.0 |\n| 8:30 am | Core PPI | April | -0.2% | 0.3% | 0.2% |\n| 8:30 am | PPI year over year |  | 2.4% | -- | 3.4% |\n| 8:30 am | Core PPI year over year |  | 2.9% | -- | 3.5% |\n| 8:30 am | [Empire State manufacturing survey](https://www.newyorkfed.org/survey/empire/empiresurvey_overview#tabs-2) | May | -9.2 | -9.0 | -8.1 |\n| 8:30 am | [Philadelphia Fed manufacturing survey](https://www.philadelphiafed.org/surveys-and-data/regional-economic-analysis/mbos-2025-05) | May | -4% | -10.0 | -26.4 |\n| 8:40 am | [Fed Chairman Jerome Powell speech](https://www.marketwatch.com/story/powell-says-inflation-could-be-more-volatile-in-the-future-86d136b5?mod=economy-politics) |  |  |  |  |\n| 9:15 am | [Industrial production](https://www.marketwatch.com/story/industrial-output-was-flat-in-april-with-growing-stress-from-tariffs-74625bf2?mod=home_ln) | April | 0.0 | 0.1% | -0.3% |\n| 9:15 am | Capacity utilization | April | 77.7% | 77.8% | 77.8% |\n| 10:00 am | [Business inventories](https://www.census.gov/mtis/index.html) | March | 0.1% | 0.2% | 0.2% |\n| 10:00 am | [Home builder confidence index](https://www.nahb.org/news-and-economics/housing-economics/indices/housing-market-index) | May | 34 | 40 | 40 |\n| 2:05 pm | Fed Governor Michael Barr speech |  |  |  |  |\n| **FRIDAY, MAY 16** |  |  |  |  |  |\n| 8:30 am | [Import price index](https://www.marketwatch.com/story/imported-goods-costs-showing-signs-of-tariff-related-price-pressures-02104621?mod=economy-politics) | April | 0.1% | -0.4% | -0.4% |\n| 8:30 am | Import price index minus fuel | April | 0.4% | -- | -0.1% |\n| 8:30 am | [Housing starts](https://www.marketwatch.com/story/home-builders-and-buyers-face-bleak-picture-weak-housing-starts-illustrate-the-problem-e502967f?mod=home_ln) | April | 1.36 million | 1.36 million | 1.34 million |\n| 8:30 am | Building permits | April | 1.41 million | 1.45 million | 1.48 million |\n| 10:00 am | [Consumer sentiment (prelim)](https://www.marketwatch.com/story/consumer-sentiment-falls-for-5th-straight-month-in-may-as-inflation-worries-grow-58e124d8?mod=home_ln) | May | 50.8 | 53.5 | 52.2 |\n\nThe median forecasts in this calendar come from surveys of economists conducted by Dow Jones Newswires and The Wall Street Journal.\n\nAll statistics in this calendar are in expressed in nominal terms unless labeled "real." "Real" statistics are inflation-adjusted using the most relevant deflator. "SAAR" means seasonally adjusted annual rate.\n\nClick on the links to read MarketWatch coverage of the data and speeches.\n\n[![Read full story](https://images.mktw.net/im-25629701?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/new-home-sales-rii-55cc866f?mod=u.s.-economic-calendar)\n\n### [Buyers rushed into the market for new homes in April, pushing sales to highest level in three years](https://www.marketwatch.com/story/new-home-sales-rii-55cc866f?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-80878575?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/mortgage-rates-rise-to-a-three-month-high-as-treasury-yields-surge-e0e1b978?mod=u.s.-economic-calendar)\n\n### [Home sales poised to slump even more as mortgage rates hit three-month high](https://www.marketwatch.com/story/mortgage-rates-rise-to-a-three-month-high-as-treasury-yields-surge-e0e1b978?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-54768127?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/buyers-are-gaining-the-upper-hand-in-a-shifting-housing-market-everybody-wants-a-deal-c880e75f?mod=u.s.-economic-calendar)\n\n### [Buyers are gaining the upper hand in a shifting housing market. ‘Everybody wants a deal.’](https://www.marketwatch.com/story/buyers-are-gaining-the-upper-hand-in-a-shifting-housing-market-everybody-wants-a-deal-c880e75f?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-585731?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/trump-recession-is-off-the-table-but-trouble-not-over-for-u-s-economy-e19ea3ea?mod=u.s.-economic-calendar)\n\n### [Trump recession is off the table — but trouble is not over for the U.S. economy](https://www.marketwatch.com/story/trump-recession-is-off-the-table-but-trouble-not-over-for-u-s-economy-e19ea3ea?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-85472055?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/imported-goods-costs-showing-signs-of-tariff-related-price-pressures-02104621?mod=u.s.-economic-calendar)\n\n### [Imported-goods costs showing signs of tariff-related price pressures](https://www.marketwatch.com/story/imported-goods-costs-showing-signs-of-tariff-related-price-pressures-02104621?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-528299?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/home-builders-and-buyers-face-bleak-picture-weak-housing-starts-illustrate-the-problem-e502967f?mod=u.s.-economic-calendar)\n\n### [Home builders and buyers face bleak picture this spring. Weak housing starts illustrate why.](https://www.marketwatch.com/story/home-builders-and-buyers-face-bleak-picture-weak-housing-starts-illustrate-the-problem-e502967f?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-20174665?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/this-social-security-question-is-so-hard-that-even-financial-pros-get-stumped-7c63f1f6?mod=u.s.-economic-calendar)\n\n### [This Social Security question is so hard that even financial pros get stumped](https://www.marketwatch.com/story/this-social-security-question-is-so-hard-that-even-financial-pros-get-stumped-7c63f1f6?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-88436405?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/is-now-a-good-time-to-buy-an-iphone-b77772f9?mod=u.s.-economic-calendar)\n\n### [Is now a good time to buy an iPhone?](https://www.marketwatch.com/story/is-now-a-good-time-to-buy-an-iphone-b77772f9?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-91024457?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/the-mother-of-all-credit-squeezes-is-coming-hang-onto-your-wallet-26a2280d?mod=u.s.-economic-calendar)\n\n### [The ‘mother of all credit squeezes’ is coming — hang onto your wallet](https://www.marketwatch.com/story/the-mother-of-all-credit-squeezes-is-coming-hang-onto-your-wallet-26a2280d?mod=u.s.-economic-calendar)\n\n[![Go to video](https://images.mktw.net/im-91522384?width=1280&height=720)](https://www.marketwatch.com/video/need-to-know/why-the-us-dollar-is-sinking-and-what-it-means-for-investors/B72E4A81-D8A6-4518-8293-A06C4F33A67B.html?mod=u.s.-economic-calendar)\n\n### [Why the U.S. dollar is sinking — and what it means for investors](https://www.marketwatch.com/video/need-to-know/why-the-us-dollar-is-sinking-and-what-it-means-for-investors/B72E4A81-D8A6-4518-8293-A06C4F33A67B.html?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-62348854?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/we-used-ai-for-retirement-planning-advice-and-were-surprised-by-what-we-found-dc64e936?mod=u.s.-economic-calendar)\n\n### [We used AI for retirement planning advice and were surprised by what we found](https://www.marketwatch.com/story/we-used-ai-for-retirement-planning-advice-and-were-surprised-by-what-we-found-dc64e936?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-09670237?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/my-daughters-boyfriend-a-guest-in-my-home-offered-to-powerwash-part-of-my-house-then-demanded-money-9ad16f4c?mod=u.s.-economic-calendar)\n\n### [My daughter’s boyfriend, a guest in my home, offered to powerwash part of my house — then demanded money](https://www.marketwatch.com/story/my-daughters-boyfriend-a-guest-in-my-home-offered-to-powerwash-part-of-my-house-then-demanded-money-9ad16f4c?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-08077063?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/medicare-advantage-crisis-deepens-as-dr-oz-launches-aggressive-audits-3485aaa9?mod=u.s.-economic-calendar)\n\n### [Medicare Advantage crisis deepens as Dr. Oz launches ‘aggressive’ audits](https://www.marketwatch.com/story/medicare-advantage-crisis-deepens-as-dr-oz-launches-aggressive-audits-3485aaa9?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-44787285?size=1.777777777777778&width=1240)](https://www.marketwatch.com/picks/my-80-year-old-friend-who-worked-for-the-federal-government-has-only-taken-his-rmds-once-now-he-wants-to-do-whats-right-but-how-abcd866a?mod=u.s.-economic-calendar)\n\n### [My 80-year-old friend, who worked for the federal government, has only taken his RMDs once. Now he ‘wants to do what’s right,’ but how?](https://www.marketwatch.com/picks/my-80-year-old-friend-who-worked-for-the-federal-government-has-only-taken-his-rmds-once-now-he-wants-to-do-whats-right-but-how-abcd866a?mod=u.s.-economic-calendar)\n\n[![Go to video](https://images.mktw.net/im-66852226?width=1280&height=720)](https://www.marketwatch.com/video/mounting-risks-whats-threatening-us-markets-in-2025/92A14BBA-5D4A-4AD7-97B4-27CA6D09AAF2.html?mod=u.s.-economic-calendar)\n\n### [Mounting risks: what’s threatening U.S. markets in 2025?](https://www.marketwatch.com/video/mounting-risks-whats-threatening-us-markets-in-2025/92A14BBA-5D4A-4AD7-97B4-27CA6D09AAF2.html?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-78678958?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/heres-why-gamestops-stock-has-been-in-play-again-its-not-a-meme-thing-this-time-9e5a5be8?mod=u.s.-economic-calendar)\n\n### [Here’s why GameStop’s stock has been in play again. It’s not a meme thing this time.](https://www.marketwatch.com/story/heres-why-gamestops-stock-has-been-in-play-again-its-not-a-meme-thing-this-time-9e5a5be8?mod=u.s.-economic-calendar)\n\n×\n\nClose Trending Tickers bar\n\n- [LITM$3.90\\\\\n\\\\\n14.37%0.49](https://www.marketwatch.com/investing/stock/litm?mod=trending-tickers)\n- [DOUG$2.93\\\\\n\\\\\n36.92%0.79](https://www.marketwatch.com/investing/stock/doug?mod=trending-tickers)\n- [LTRY$2.09\\\\\n\\\\\n30.66%0.49](https://www.marketwatch.com/investing/stock/ltry?mod=trending-tickers)\n- [LTBR$14.70\\\\\n\\\\\n37.90%4.04](https://www.marketwatch.com/investing/stock/ltbr?mod=trending-tickers)\n\n[Access Premium Tools](https://get.investors.com/product-overview/?src=A00619&refcode=Site%20placement%7CMarketWatch%7CMarketWatch%7C2023%7CRecurring%7COther%2FNA%7C0%7C%7C992173)\n\nSearchClear\n\nSearch\n\n[Advanced Search](https://www.marketwatch.com/search?q=)\n\nLoading...\n\n|\n|\n\nLoading...\n\n|\n|\n\n### No Recent Tickers\n\nVisit a quote page and your recently viewed tickers will be displayed here.\n\nSearch Tickers\n\n| Symbol | Price | Change | % Chg |\n| --- | --- | --- | --- |\n\nAll NewsArticlesVideoPodcasts\n\n×\n\n×\n\nThis browser is no longer supported at MarketWatch. For the best MarketWatch.com experience, please update to a modern browser.\n\n[Chrome](https://www.google.com/chrome/) [Safari](https://support.apple.com/downloads/safari) [Firefox](https://www.mozilla.org/en-US/firefox/) [Edge](https://www.microsoft.com/en-us/windows/microsoft-edge)\n\n[iframe](about:blank)' html=None rawHtml=None links=None extract=None json=<function BaseModel.json at 0x7b2738d56560> screenshot=None metadata={'fb:app_id': '283204329838', 'uac-config': '%7b%22breakpoints%22%3a%7b%22at4units%22%3a0%2c%22at8units%22%3a656%2c%22at12units%22%3a976%2c%22at16units%22%3a1296%7d%7d', 'ogTitle': 'U.S. Economic Calendar - MarketWatch', 'referrer': 'no-referrer-when-downgrade', 'twitter:description': 'U.S. economic calendar consensus forecasts from MarketWatch.', 'theme-color': '#2e2e2f', 'og:site_name': 'MarketWatch', 'parsely-tags': 'PageType: Standard, Region: United States, Subject: Economic News, Subject: Political/General News, Related: economy-_-politics, Related: economic-report, Related: economic-outlook, Related: economic-preview, Related: capitol-report, Related: forecaster-of-the-month, Related: rex-nutting-author, Related: trump-today, Related: need-to-know, mw-page', 'description': 'U.S. economic calendar consensus forecasts from MarketWatch.', 'og:image': 'https://mw3.wsj.net/mw5/content/logos/mw_logo_social.png', 'parsely-title': 'U.S. Economic Calendar - MarketWatch', 'apple-itunes-app': 'app-id=336693422', 'fb:pages': '131043201847', 'chartjs': 'https://sts3.wsj.net/bucket-a/maggie/static/js/chart-69a43a7fa0.min.js', 'viewport': 'width=device-width, initial-scale=1.0', 'robots': 'noarchive, nocache, noodp', 'twitter:image:height': '630', 'parsely-type': 'post', 'og:url': 'https://www.marketwatch.com/economy-politics/calendar', 'article:publisher': 'https://www.facebook.com/marketwatch', 'ogSiteName': 'MarketWatch', 'og:title': 'U.S. Economic Calendar - MarketWatch', 'ogUrl': 'https://www.marketwatch.com/economy-politics/calendar', 'twitter:domain': 'marketwatch.com', 'language': 'en', 'twitter:image': 'https://mw3.wsj.net/mw5/content/logos/mw_logo_social.png', 'parsely-link': 'https://www.marketwatch.com/economy-politics/calendar', 'favicon': 'https://mw4.wsj.net/mw5/content/images/favicons/apple-touch-icon.png', 'title': 'U.S. Economic Calendar - MarketWatch', 'twitter:site:id': '624413', 'twitter:creator': '@marketwatch', 'keywords': 'united states, economic news, political, general news', 'twitter:image:width': '1200', 'twitter:card': 'summary_large_image', 'parsely-section': 'Economy & Politics', 'ogImage': 'https://mw3.wsj.net/mw5/content/logos/mw_logo_social.png', 'scrapeId': '006f79e8-7d40-46c3-8d4a-5dcb0eecb8e9', 'sourceURL': 'https://www.marketwatch.com/economy-politics/calendar', 'url': 'https://www.marketwatch.com/economy-politics/calendar', 'statusCode': 200, 'proxyUsed': 'basic'} actions=None title=None description=None changeTracking=None success=True warning=None error=None"""
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
            parsed = json.loads(cleaned)
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
            # TODO: This is for testing purpose
            state.current_event = state.upcoming_events[0]
            logger.info(f"EventsAgent: Set current_event to: {state.current_event.name}")
        else:
            logger.warning("EventsAgent: No upcoming events were added to the state.")
            state.current_event = None # Ensure current_event is None if no upcoming_events

        return state
