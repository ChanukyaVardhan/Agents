# Macro Events Agent

## Overview

The Macro Events Agent is an LLM AI Agent application designed to help users stay informed about upcoming macroeconomic events. It automatically fetches event data from online economic calendars, identifies important events, searches for relevant news and analysis, generates concise summaries, and creates Google Calendar entries with this preparatory information.

This allows users to be well-prepared for significant market-moving events.

## Setup and Installation

### Prerequisites

- Python 3.9+ (recommended)
- Anaconda or Miniconda installed
- Access to a Google account and Google Calendar
- API keys for:
  - OpenRouter (for LLM access)
  - Firecrawl (for web scraping)

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd <your-repository-directory>/macro-events-agent
```

### 2. Create and Activate a Conda Environment

Use `conda` to create a new environment:

```bash
conda create -n macro-agent python=3.9
conda activate macro-agent
```

### 3. Install Dependencies

Install required packages using pip inside the conda environment:

```bash
pip install -r requirements.txt
```

### 4. Configuration

#### a. Environment Variables

The agent uses environment variables for API keys and other configurations. Create a `.env` file in the `macro-events-agent` directory by copying the example:

```bash
cp .env.example .env
```

Now, edit the `.env` file and add your actual API keys:

```
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
FIRE_CRAWL_API=YOUR_FIRE_CRAWL_API_KEY
MACRO_AGENT_CALENDAR_ID=YOUR_GOOGLE_CALENDAR_ID
```

*   `OPENROUTER_API_KEY`: Your API key from [OpenRouter.ai](https://openrouter.ai/).
*   `FIRE_CRAWL_API`: Your API key from [Firecrawl.dev](https://firecrawl.dev/).
*   `MACRO_AGENT_CALENDAR_ID`: The ID of the Google Calendar you want the agent to use. You can find this in your Google Calendar settings (usually looks like an email address, or 'primary' for your main calendar).

#### b. Google Calendar API Setup

The agent needs permission to access your Google Calendar.

1.  **Enable the Google Calendar API**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Search for "Google Calendar API" in the API Library and enable it for your project.
2.  **Create OAuth 2.0 Credentials**:
    *   Go to "APIs & Services" > "Credentials".
    *   Click "Create Credentials" > "OAuth client ID".
    *   If prompted, configure the OAuth consent screen. For "User type", select "External" if you are using a personal Gmail account, or "Internal" if you are part of a Google Workspace organization. Add your email as a test user.
    *   Choose "Desktop app" as the application type.
    *   Name your client ID (e.g., "MacroEventsAgentClient").
    *   Download the JSON file. Rename it to `calendarapi_credentials.json` and place it in the `macro-events-agent/api_keys/` directory. (Create the `api_keys` directory if it doesn't exist).
3.  **First Run and Authentication**:
    *   The first time you run the agent (`python main.py`), it will attempt to open a new tab in your web browser to authorize access to your Google Calendar.
    *   Follow the prompts to allow access.
    *   Upon successful authorization, a `calendarapi_token.json` file will be created in the `macro-events-agent/api_keys/` directory. This token will be used for future authentications. **Keep this file secure and do not commit it to version control.**

## Directory Structure

```
macro-events-agent/
├── agents/                # Contains the different AI agents (Events, Search, Summarizer)
│   ├── events_agent.py
│   ├── search_agent.py
│   └── summarizer_agent.py
├── api_keys/              # Stores Google Calendar API credentials (token should be .gitignored)
│   ├── calendarapi_credentials.json (template or your downloaded file)
│   └── calendarapi_token.json (generated on first run, .gitignored)
├── output/                # Contains output files, like trace logs
│   └── output.txt
├── .env                   # Local environment variables (gitignored)
├── .env.example           # Example environment variables file
├── .gitignore             # Specifies intentionally untracked files
├── calendar_tools.py      # Handles Google Calendar API interactions
├── llm.py                 # Client for interacting with LLMs (OpenRouter)
├── main.py                # Main script to run the agent workflow
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── state.py               # Defines the data structures (GlobalState, Event, etc.)
└── utils.py               # Utility functions (e.g., logging, file I/O)
```

## Usage

Ensure your virtual environment is activated and your `.env` file is correctly configured.

To run the agent:

```bash
python main.py
```

