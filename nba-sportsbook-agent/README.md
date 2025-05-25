# NBA Sportsbook Agent

## Overview

The NBA Sportsbook Agent is an LLM powered AI agent system designed to assist users with NBA betting insights. It analyzes NBA player performance data, retrieves current betting odds, and processes user queries to suggest potential player market bets.

The system leverages LangGraph to manage a multi-agent workflow, where distinct agents collaborate to gather data, resolve entities across different data sources (NBA stats APIs and Odds APIs), and perform analysis to answer user questions.

## Setup and Installation

### Prerequisites

*   Python 3.9+ (recommended)
*   Anaconda or Miniconda (optional, but recommended for environment management)
*   API keys for:
    *   **OpenRouter**: For Large Language Model (LLM) access. Sign up at [OpenRouter.ai](https://openrouter.ai/).
    *   **The Odds API**: For fetching betting odds. Sign up at [The Odds API](https://the-odds-api.com/).
*   The `nba_api` Python package is used for NBA statistics and does not require an API key.

### 1. Clone the Repository

```bash
git clone <your-repository-url> # Replace with the actual URL of your repository
cd nba-sportsbook-agent
```

### 2. Create and Activate a Conda Environment (Recommended)

If you have Conda installed, create and activate a new environment:

```bash
conda create -n nba-agent python=3.9
conda activate nba-agent
```

### 3. Install Dependencies

Install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

### 4. Configuration (Environment Variables)

The agent uses environment variables for API keys and other configurations.

First, copy the example environment file:

```bash
cp .env.example .env
```

Now, edit the `.env` file with your actual API keys and desired configurations:

```
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
ODDS_API_KEY=YOUR_ODDS_API_KEY
```

*   `OPENROUTER_API_KEY`: Your API key from [OpenRouter.ai](https://openrouter.ai/).
*   `ODDS_API_KEY` with your key from The Odds API.

## Directory Structure

```
nba-sportsbook-agent/
├── agents/                       # Contains the different AI agents
│   ├── data_agent.py             # Agent for fetching necessary data (games, odds, player stats)
│   ├── metadata_resolver_agent.py # Agent for matching data between NBA stats and odds APIs
│   └── analysis_agent.py         # Agent for analyzing data and formulating betting insights
├── output/                       # Default directory for trace logs
│   └── output.txt                # Example trace log file
├── .env                          # Local environment variables (gitignored)
├── .env.example                  # Example environment variables file
├── .gitignore                    # Specifies intentionally untracked files
├── llm.py                        # Client for interacting with LLMs (e.g., OpenRouter)
├── main.py                       # Main script to run the agent workflow
├── nba_stats.py                  # Contains NBAStatsAPI class for fetching data via nba_api
├── odds.py                       # Contains OddsAPIClient class for fetching data from The Odds API
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── state.py                      # Defines GlobalState and other Pydantic data structures
├── tools.py                      # Provides tools for agents (uses NBAStatsAPI, OddsAPIClient)
└── utils.py                      # Utility functions (e.g., logging, file I/O)
```

## Usage

Ensure your virtual environment (if using Conda) is activated and your `.env` file is correctly configured with your API keys.

To run the NBA Sportsbook Agent:

```bash
python main.py
```
