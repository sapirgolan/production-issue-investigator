# Production Issue Investigator

An AI-powered agent for investigating production issues using Claude Agent SDK, DataDog, and GitHub.

## Features

- **Main Orchestrator Agent**: Coordinates the investigation process
- **DataDog Retriever Sub-Agent**: Fetches logs and metrics from DataDog
- **Deployment Checker Sub-Agent**: Checks recent deployments and releases
- **Code Checker Sub-Agent**: Analyzes code changes and commits

## Requirements

- Python 3.9 or higher
- UV (recommended) or pip for dependency management
- API keys for:
  - Anthropic (Claude)
  - DataDog
  - GitHub (optional)

## Installation

### Using UV (Recommended)

UV is a fast Python package installer and runner. Install it first if you haven't:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then run the project directly with UV (it will automatically set up a virtual environment and install dependencies):

```bash
# Run directly with UV
uv run main.py

# Or sync dependencies and run
uv sync
uv run main.py
```

### Using Traditional Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Unix/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys:
   ```bash
   ANTHROPIC_API_KEY=your_api_key_here
   DATADOG_API_KEY=your_datadog_api_key
   DATADOG_APP_KEY=your_datadog_app_key
   GITHUB_TOKEN=your_github_token_here
   ```

## Project Structure

```
production-issue-investigator/
├── main.py                      # Main entry point
├── agents/                      # Agent modules
│   ├── main_agent.py           # Main orchestrator
│   ├── datadog_retriever.py    # DataDog sub-agent
│   ├── deployment_checker.py   # Deployment sub-agent
│   └── code_checker.py         # Code sub-agent
├── utils/                       # Utility modules
│   ├── datadog_api.py          # DataDog API wrapper
│   ├── github_helper.py        # GitHub helper
│   ├── time_utils.py           # Time utilities
│   └── report_generator.py     # Report generation
├── logs/                        # Application logs
├── requirements.txt             # Python dependencies
├── pyproject.toml              # Project metadata for UV
├── .env                         # Environment variables (not in git)
└── .env.example                # Example environment file
```

## Usage

### Basic Usage

```bash
# Using UV
uv run main.py

# Using Python directly
python main.py
```

### Development

The project follows these conventions:
- All dependencies are pinned to specific versions in `requirements.txt`
- Timezone conversion utilities for Tel Aviv ↔ UTC
- Structured logging to `logs/agent.log`
- Environment variables loaded from `.env`

## Dependencies

All dependencies are specified with minimum versions for compatibility:

- `anthropic>=0.40.0` - Anthropic Python client (dependency of SDK)
- `claude-agent-sdk>=0.1.35` - Claude Agent SDK for building autonomous agents
- `python-dotenv>=1.0.0` - Environment variable management
- `requests>=2.31.0` - HTTP API calls
- `PyGithub>=2.1.1` - GitHub API client
- `python-dateutil>=2.8.2` - Flexible datetime parsing
- `pytz>=2023.3` - Timezone handling

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]
