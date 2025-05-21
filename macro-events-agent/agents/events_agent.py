from state import GlobalState, SearchQueryResult, Event
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field
from typing import List, Dict
from utils import write_to_file
from utils import logger
import json
import llm
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
    role: str = Field(..., description="The role of the message sender.")
    content: str = Field(..., description="The content of the message.")


class EventsAgent:
    def __init__(self, output_trace_path: str):
        self.output_trace_path = output_trace_path

        self.firecrawl_app = FirecrawlApp(api_key=FIRE_CRAWL_API)

    def trace(self, role: str, content: str) -> None:
        write_to_file(path=self.output_trace_path, content=f"{role}: {content}\n")

    def ask_llm(self, prompt: str) -> str:
        self.trace("user", prompt)

        contents = [Message(role='user', content=prompt)]
        response = llm.response(contents)

        return str(response) if response else "No response from LLM"

    def build_prompt(self, state: GlobalState) -> str:
        # Format calendar events with the new format
        if state.events_in_calendar:
            calendar_events_formatted = "\n".join([
                f"\n- **Event Name**: {event.name}\n- **Event Date**: {event.date}\n"
                for event in state.events_in_calendar
            ])
        else:
            calendar_events_formatted = "No events in the calendar"


        # TODO: We can use multiple urls and scrape multiple of them.
        market_watch_us_calendar_url = "https://www.marketwatch.com/economy-politics/calendar"
        scrape_result = self.firecrawl_app.scrape_url(
            url=market_watch_us_calendar_url,
            formats=["markdown"],
            only_main_content= True
        )
        # scrape_result = """[Economy & Politics](https://www.marketwatch.com/economy-politics?mod=u.s.-economic-calendar)\n\n- [The Fed](https://www.marketwatch.com/economy-politics/federal-reserve?mod=u.s.-economic-calendar)\n- [U.S. Economic Calendar](https://www.marketwatch.com/economy-politics/calendars/economic?mod=u.s.-economic-calendar)\n- [Economic Report](https://www.marketwatch.com/column/economic-report?mod=u.s.-economic-calendar)\n- [Inflation](https://www.marketwatch.com/economy-politics/inflation?mod=u.s.-economic-calendar)\n- [Washington Watch](https://www.marketwatch.com/column/washington-watch?mod=u.s.-economic-calendar)\n\n1. [Home](https://www.marketwatch.com/?mod=u.s.-economic-calendar)\n2. [Economy & Politics](https://www.marketwatch.com/economy-politics?mod=u.s.-economic-calendar)\n3. U.S. Economic Calendar\n\n# This Week\'s Major U.S. Economic Reports & Fed Speakers\n\n| Time (ET) | Report | Period | Actual | Median Forecast | Previous |\n| --- | --- | --- | --- | --- | --- |\n| **MONDAY, MAY 19** |  |  |  |  |  |\n| 8:45 am | New York Fed President John Williams speech |  |  |  |  |\n| 8:45 am | [Fed Vice Chair Philip Jefferson speech](https://www.federalreserve.gov/newsevents/speech/jefferson20250519a.htm) |  |  |  |  |\n| 10:00 am | [U.S. leading economic indicators](https://www.conference-board.org/topics/us-leading-indicators) | April | -1.0% | -0.9% | -0.8% |\n| **TUESDAY, MAY 20** |  |  |  |  |  |\n| 9:00 am | [Richmond Fed President Tom Barkin speech](https://www.richmondfed.org/press_room/speeches/thomas_i_barkin/2025/barkin_speech_20250520) |  |  |  |  |\n| 9:30 am | Boston Fed President Susan Collins participates in Fed Listens event |  |  |  |  |\n| 1:00 pm | [St. Louis Fed President Alberto Musalem speech](https://www.stlouisfed.org/from-the-president/remarks/2025/economic-conditions-and-monetary-policy-remarks-economic-club-of-minnesota) |  |  |  |  |\n| 5:00 pm | Federal Reserve Governor Adriana Kugler speech |  |  |  |  |\n| **WEDNESDAY, MAY 21** |  |  |  |  |  |\n| 12:15 pm | Richmond Fed President Tom Barkin and Fed Governor Michelle Bowman take part in Fed Listens event |  |  |  |  |\n| **THURSDAY, MAY 22** |  |  |  |  |  |\n| 8:30 am | Initial jobless claims | May 17 |  | 230,000 | 229,000 |\n| 9:45 am | S&P flash U.S. services PMI | May |  | 50.6 | 50.8 |\n| 9:45 am | S&P flash U.S. manufacturing PMI | May |  | 49.8 | 50.2 |\n| 10:00 am | Existing home sales | April |  | 4.13 million | 4.02 million |\n| 2:00 pm | New York Fed President John Williams speech |  |  |  |  |\n| **FRIDAY, MAY 23** |  |  |  |  |  |\n| 9:35 am | Kansas City Fed President Jeff Schmid speech |  |  |  |  |\n| 10:00 am | New home sales | April |  | 695,000 | 724,000 |\n| 12:00 pm | Federal Reserve Governor Lisa Cook speech |  |  |  |  |\n| **SUNDAY, MAY 25** |  |  |  |  |  |\n| 2:40 pm | Federal Reserve Chair Jerome Powell commencement address |  |  |  |  |\n\n# Next Week\'s Major U.S. Economic Reports & Fed Speakers\n\n| Time (ET) | Report | Period | Actual | Median Forecast | Previous |\n| --- | --- | --- | --- | --- | --- |\n| **MONDAY, MAY 26** |  |  |  |  |  |\n|  | None scheduled, Memorial Day holiday |  |  |  |  |\n| **TUESDAY, MAY 27** |  |  |  |  |  |\n| 8:30 am | Durable-goods orders | April |  |  | 9.2% |\n| 8:30 am | Durable-goods minus transportation | April |  |  | 0.0% |\n| 9:00 am | S&P CoreLogic Case-Shiller home price index (20 cities) | March |  |  | 4.5% |\n| 10:00 am | Consumer confidence | May |  |  | 86.0 |\n| **WEDNESDAY, MAY 28** |  |  |  |  |  |\n| 2:00 pm | Minutes of Fed\'s May FOMC meeting |  |  |  |  |\n| **THURSDAY, MAY 29** |  |  |  |  |  |\n| 8:30 am | Initial jobless claims | May 24 |  |  |  |\n| 8:30 am | GDP (First revision) | Q1 |  |  | -0.3% |\n| 10:00 am | Pending home sales | April |  | -- | 6.1% |\n| **FRIDAY, MAY 30** |  |  |  |  |  |\n| 8:30 am | Personal income | April |  |  | 0.5% |\n| 8:30 am | Personal spending | April |  |  | 0.7% |\n| 8:30 am | PCE index | April |  |  | 0.0% |\n| 8:30 am | PCE (year-over-year) |  |  |  | 2.3% |\n| 8:30 am | Core PCE index | April |  |  | 0.0% |\n| 8:30 am | Core PCE (year-over-year) |  |  |  | 2.6% |\n| 8:30 am | Advanced U.S. trade balance in goods | April |  |  | -$163.2B |\n| 8:30 am | Advanced retail inventories | April |  |  | -0.1% |\n| 8:30 am | Advanced wholesale inventories | April |  |  | 0.4% |\n| 9:45 am | Chicago Business Barometer (PMI) | May |  |  | 44.6 |\n| 10:00 am | Consumer sentiment (final) | May |  |  | 50.8 |\n\n# Last Week\'s Major U.S. Economic Reports & Fed Speakers\n\n| Time (ET) | Report | Period | Actual | Median Forecast | Previous |\n| --- | --- | --- | --- | --- | --- |\n| **MONDAY, MAY 12** |  |  |  |  |  |\n| 10:25 am | [Fed Governor Adriana Kugler speech](https://www.federalreserve.gov/newsevents/speech/kugler20250512a.htm) |  |  |  |  |\n| 2:00 pm | [Monthly U.S. federal budget](https://www.fiscal.treasury.gov/reports-statements/mts/) | April | $258B | $256B | $210B |\n| **TUESDAY, MAY 13** |  |  |  |  |  |\n| 6:00 am | [NFIB optimism index](https://www.nfib.com/news/monthly_report/sbet/) | April | 95.8 | 95.0 | 97.4 |\n| 8:30 am | [Consumer price index](https://www.marketwatch.com/story/consumer-prices-post-mild-increase-in-april-but-trade-wars-likely-to-add-to-inflation-despite-reduced-tariffs-32757558?mod=home_ln) | April |  | 0.2% | -0.1% |\n| 8:30 am | CPI year over year |  |  | 2.4% | 2.4% |\n| 8:30 am | Core CPI | April |  | 0.3% | 0.1% |\n| 8:30 am | Core CPI year over year |  |  | 2.8% | 2.8% |\n| **WEDNESDAY, MAY 14** |  |  |  |  |  |\n| 5:15 am | [Fed Governor Christopher Waller speech](https://www.federalreserve.gov/newsevents/speech/waller20250514a.htm) |  |  |  |  |\n| 9:10 am | [Fed Vice Chair Philip Jefferson speech](https://www.federalreserve.gov/newsevents/speech/jefferson20250514a.htm) |  |  |  |  |\n| 5:40 pm | San Francisco Fed President Mary Daly speech |  |  |  |  |\n| **THURSDAY, MAY 15** |  |  |  |  |  |\n| 8:30 am | [Initial jobless claims](https://www.marketwatch.com/story/jobless-claims-hold-steady-in-latest-week-continuing-to-signal-healthy-labor-market-db1f0f84?mod=home_ln) | May 10 | 229,000 | 226,000 | 229,000 |\n| 8:30 am | [U.S. retail sales](https://www.marketwatch.com/story/retail-sales-peter-out-in-april-as-tariffs-kicked-in-60dcbaf4?mod=home_ln) | April | 0.1% | 0.1% | 1.7% |\n| 8:30 am | Retail sales minus autos | April | 0.1% | 0.3% | 0.8% |\n| 8:30 am | [Producer price index](https://www.marketwatch.com/story/wholesale-inflation-shows-biggest-drop-since-2020-but-its-unlikely-to-last-f063a765?mod=economy-politics) | April | 0.5% | 0.3% | -0.0 |\n| 8:30 am | Core PPI | April | -0.2% | 0.3% | 0.2% |\n| 8:30 am | PPI year over year |  | 2.4% | -- | 3.4% |\n| 8:30 am | Core PPI year over year |  | 2.9% | -- | 3.5% |\n| 8:30 am | [Empire State manufacturing survey](https://www.newyorkfed.org/survey/empire/empiresurvey_overview#tabs-2) | May | -9.2 | -9.0 | -8.1 |\n| 8:30 am | [Philadelphia Fed manufacturing survey](https://www.philadelphiafed.org/surveys-and-data/regional-economic-analysis/mbos-2025-05) | May | -4% | -10.0 | -26.4 |\n| 8:40 am | [Fed Chairman Jerome Powell speech](https://www.marketwatch.com/story/powell-says-inflation-could-be-more-volatile-in-the-future-86d136b5?mod=economy-politics) |  |  |  |  |\n| 9:15 am | [Industrial production](https://www.marketwatch.com/story/industrial-output-was-flat-in-april-with-growing-stress-from-tariffs-74625bf2?mod=home_ln) | April | 0.0 | 0.1% | -0.3% |\n| 9:15 am | Capacity utilization | April | 77.7% | 77.8% | 77.8% |\n| 10:00 am | [Business inventories](https://www.census.gov/mtis/index.html) | March | 0.1% | 0.2% | 0.2% |\n| 10:00 am | [Home builder confidence index](https://www.nahb.org/news-and-economics/housing-economics/indices/housing-market-index) | May | 34 | 40 | 40 |\n| 2:05 pm | Fed Governor Michael Barr speech |  |  |  |  |\n| **FRIDAY, MAY 16** |  |  |  |  |  |\n| 8:30 am | [Import price index](https://www.marketwatch.com/story/imported-goods-costs-showing-signs-of-tariff-related-price-pressures-02104621?mod=economy-politics) | April | 0.1% | -0.4% | -0.4% |\n| 8:30 am | Import price index minus fuel | April | 0.4% | -- | -0.1% |\n| 8:30 am | [Housing starts](https://www.marketwatch.com/story/home-builders-and-buyers-face-bleak-picture-weak-housing-starts-illustrate-the-problem-e502967f?mod=home_ln) | April | 1.36 million | 1.36 million | 1.34 million |\n| 8:30 am | Building permits | April | 1.41 million | 1.45 million | 1.48 million |\n| 10:00 am | [Consumer sentiment (prelim)](https://www.marketwatch.com/story/consumer-sentiment-falls-for-5th-straight-month-in-may-as-inflation-worries-grow-58e124d8?mod=home_ln) | May | 50.8 | 53.5 | 52.2 |\n\nThe median forecasts in this calendar come from surveys of economists conducted by Dow Jones Newswires and The Wall Street Journal.\n\nAll statistics in this calendar are in expressed in nominal terms unless labeled "real." "Real" statistics are inflation-adjusted using the most relevant deflator. "SAAR" means seasonally adjusted annual rate.\n\nClick on the links to read MarketWatch coverage of the data and speeches.\n\n[![Read full story](https://images.mktw.net/im-585731?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/trump-recession-is-off-the-table-but-trouble-not-over-for-u-s-economy-e19ea3ea?mod=u.s.-economic-calendar)\n\n### [Trump recession is off the table — but trouble is not over for the U.S. economy](https://www.marketwatch.com/story/trump-recession-is-off-the-table-but-trouble-not-over-for-u-s-economy-e19ea3ea?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-85472055?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/imported-goods-costs-showing-signs-of-tariff-related-price-pressures-02104621?mod=u.s.-economic-calendar)\n\n### [Imported-goods costs showing signs of tariff-related price pressures](https://www.marketwatch.com/story/imported-goods-costs-showing-signs-of-tariff-related-price-pressures-02104621?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-528299?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/home-builders-and-buyers-face-bleak-picture-weak-housing-starts-illustrate-the-problem-e502967f?mod=u.s.-economic-calendar)\n\n### [Home builders and buyers face bleak picture this spring. Weak housing starts illustrate why.](https://www.marketwatch.com/story/home-builders-and-buyers-face-bleak-picture-weak-housing-starts-illustrate-the-problem-e502967f?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-49310107?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/wholesale-inflation-shows-biggest-drop-since-2020-but-its-unlikely-to-last-f063a765?mod=u.s.-economic-calendar)\n\n### [Wholesale inflation shows biggest decline since 2020, but the good news is unlikely to last](https://www.marketwatch.com/story/wholesale-inflation-shows-biggest-drop-since-2020-but-its-unlikely-to-last-f063a765?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-31528749?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/industrial-output-was-flat-in-april-with-growing-stress-from-tariffs-74625bf2?mod=u.s.-economic-calendar)\n\n### [Industrial output stalls in April in latest sign that the U.S. economy is losing steam as stress from Trump’s tariffs sets in](https://www.marketwatch.com/story/industrial-output-was-flat-in-april-with-growing-stress-from-tariffs-74625bf2?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-06346844?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/retail-sales-peter-out-in-april-as-tariffs-kicked-in-60dcbaf4?mod=u.s.-economic-calendar)\n\n### [Retail sales petered out as tariffs kicked in, but Americans are still spending enough to keep the economy from slumping](https://www.marketwatch.com/story/retail-sales-peter-out-in-april-as-tariffs-kicked-in-60dcbaf4?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-77249656?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/why-the-next-20-year-treasury-auction-is-must-see-tv-for-investors-after-the-moodys-downgrade-ac71a676?mod=u.s.-economic-calendar)\n\n### [Why the next 20-year Treasury auction is ‘must-see TV’ for investors after the Moody’s downgrade](https://www.marketwatch.com/story/why-the-next-20-year-treasury-auction-is-must-see-tv-for-investors-after-the-moodys-downgrade-ac71a676?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-76822500?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/elon-musks-starlink-is-battling-globalstar-to-rule-the-skies-heres-the-likely-winner-a3356bba?mod=u.s.-economic-calendar)\n\n### [It’s Musk and T-Mobile Starlink vs. Apple and Globalstar in the satellite phone wars. But one stock is already the clear winner.](https://www.marketwatch.com/story/elon-musks-starlink-is-battling-globalstar-to-rule-the-skies-heres-the-likely-winner-a3356bba?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-01304707?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/trumps-1-6-trillion-spin-what-the-numbers-really-say-about-gop-tax-bill-4d4f0cee?mod=u.s.-economic-calendar)\n\n### [Trump’s $1.6 trillion claim: What the numbers really say about GOP tax bill](https://www.marketwatch.com/story/trumps-1-6-trillion-spin-what-the-numbers-really-say-about-gop-tax-bill-4d4f0cee?mod=u.s.-economic-calendar)\n\n[![Go to video](https://images.mktw.net/im-55827262?width=1280&height=720)](https://www.marketwatch.com/video/marketwatch-invests/end-of-us-exceptionalism-how-to-invest-after-the-credit-downgrade/72C3D4B4-1631-4EAD-823C-CD7C8BBFDA0D.html?mod=u.s.-economic-calendar)\n\n### [End of U.S. exceptionalism: How to invest after the credit downgrade](https://www.marketwatch.com/video/marketwatch-invests/end-of-us-exceptionalism-how-to-invest-after-the-credit-downgrade/72C3D4B4-1631-4EAD-823C-CD7C8BBFDA0D.html?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-38792060?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/jamie-dimon-says-stock-market-shows-complacency-heres-evidence-he-might-be-right-61c10aa8?mod=u.s.-economic-calendar)\n\n### [Jamie Dimon warns of stock-market ‘complacency’ as investors keep shaking off bad news. Strategists see evidence he’s right.](https://www.marketwatch.com/story/jamie-dimon-says-stock-market-shows-complacency-heres-evidence-he-might-be-right-61c10aa8?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-11073599?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/my-ex-wife-said-she-should-have-been-compensated-for-working-part-time-during-our-divorce-20-years-ago-do-i-owe-her-82421ac2?mod=u.s.-economic-calendar)\n\n### [My ex-wife said she should have been compensated for working part time during our marriage. Do I owe her?](https://www.marketwatch.com/story/my-ex-wife-said-she-should-have-been-compensated-for-working-part-time-during-our-divorce-20-years-ago-do-i-owe-her-82421ac2?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-46763636?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/my-fathers-widow-keeps-sending-me-200-checks-in-the-mail-why-would-she-do-this-a7697906?mod=u.s.-economic-calendar)\n\n### [My father’s widow keeps sending me $200 checks in the mail. Why would she do this?](https://www.marketwatch.com/story/my-fathers-widow-keeps-sending-me-200-checks-in-the-mail-why-would-she-do-this-a7697906?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-78476892?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/trump-sours-on-lifting-salt-cap-calling-it-a-gift-to-democratic-governors-cf7fbe89?mod=u.s.-economic-calendar)\n\n### [Trump sours on lifting SALT cap, calling it a gift to Democratic governors](https://www.marketwatch.com/story/trump-sours-on-lifting-salt-cap-calling-it-a-gift-to-democratic-governors-cf7fbe89?mod=u.s.-economic-calendar)\n\n[![Go to video](https://images.mktw.net/im-99340345?width=1280&height=720)](https://www.marketwatch.com/video/marketwatch-invests/gold-prices-too-rich-consider-these-alternative-precious-metals/01D5FED1-8549-48CD-A4C8-62B72FE663E2.html?mod=u.s.-economic-calendar)\n\n### [Gold prices too rich? Consider these alternative precious metals](https://www.marketwatch.com/video/marketwatch-invests/gold-prices-too-rich-consider-these-alternative-precious-metals/01D5FED1-8549-48CD-A4C8-62B72FE663E2.html?mod=u.s.-economic-calendar)\n\n[![Read full story](https://images.mktw.net/im-50434243?size=1.777777777777778&width=1240)](https://www.marketwatch.com/story/this-is-how-americans-are-blowing-their-retirement-money-again-82fb42ff?mod=u.s.-economic-calendar)\n\n### [This is how Americans are blowing their retirement money — again](https://www.marketwatch.com/story/this-is-how-americans-are-blowing-their-retirement-money-again-82fb42ff?mod=u.s.-economic-calendar)\n\n×\n\nClose Trending Tickers bar\n\n- [TOI$2.80\\\\\n\\\\\n0.67%0.02](https://www.marketwatch.com/investing/stock/toi?mod=trending-tickers)\n- [SYTA$9.01\\\\\n\\\\\n10.01%0.82](https://www.marketwatch.com/investing/stock/syta?mod=trending-tickers)\n- [BPOP$105.15\\\\\n\\\\\n0.00%0.00](https://www.marketwatch.com/investing/stock/bpop?mod=trending-tickers)\n- [KVYO$34.01\\\\\n\\\\\n0.00%0.00](https://www.marketwatch.com/investing/stock/kvyo?mod=trending-tickers)\n\n[Access Premium Tools](https://get.investors.com/product-overview/?src=A00619&refcode=Site%20placement%7CMarketWatch%7CMarketWatch%7C2023%7CRecurring%7COther%2FNA%7C0%7C%7C992173)\n\nSearchClear\n\nSearch\n\n[Advanced Search](https://www.marketwatch.com/search?q=)\n\nLoading...\n\n|\n|\n\nLoading...\n\n|\n|\n\n### No Recent Tickers\n\nVisit a quote page and your recently viewed tickers will be displayed here.\n\nSearch Tickers\n\n| Symbol | Price | Change | % Chg |\n| --- | --- | --- | --- |\n\nAll NewsArticlesVideoPodcasts\n\n×\n\n×\n\nThis browser is no longer supported at MarketWatch. For the best MarketWatch.com experience, please update to a modern browser.\n\n[Chrome](https://www.google.com/chrome/) [Safari](https://support.apple.com/downloads/safari) [Firefox](https://www.mozilla.org/en-US/firefox/) [Edge](https://www.microsoft.com/en-us/windows/microsoft-edge)\n\n[iframe](about:blank)"""
        logger.info(f"\n\n{scrape_result}\n\n")

        return PROMPT.format(
            google_calendar_events=calendar_events_formatted,
            upcoming_events=scrape_result,
            today_date = datetime.now().strftime("%Y-%m-%d")
        )

    def parse_upcoming_events(self, response: str) -> List[Dict[str, str]]:
        try:
            cleaned = response.strip().strip('`').strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
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

        # TODO: This is for testing purpose
        state.current_event = state.upcoming_events[0]

        return state
