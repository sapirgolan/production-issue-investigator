# Quick Start Guide

## Prerequisites

1. **Install UV** (if not already installed):
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Or using Homebrew
   brew install uv
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

## Running the Application

The easiest way to run the application is with UV:

```bash
# Navigate to the project directory
cd production-issue-investigator

# Run the application (UV handles everything automatically)
uv run main.py
```

That's it! UV will:
- Create a virtual environment in `.venv/`
- Install all dependencies from `pyproject.toml`
- Run the application

## What UV Does

UV is a fast Python package manager that:
- Automatically creates and manages virtual environments
- Installs dependencies much faster than pip
- Caches packages for quick reuse
- Handles dependency resolution efficiently

## Next Steps

1. **Implement the Main Agent Logic**: Edit `agents/main_agent.py` to add Claude Agent SDK integration
2. **Add DataDog Integration**: Complete the DataDog API calls in `agents/datadog_retriever.py`
3. **Add GitHub Integration**: Complete GitHub API integration in `agents/deployment_checker.py` and `agents/code_checker.py`
4. **Test the Workflow**: Create test cases and verify the agent orchestration

## Project Structure

```
production-issue-investigator/
├── main.py                      # Entry point ✅ WORKING
├── agents/                      # Agent modules ✅ STRUCTURED
│   ├── main_agent.py           # Main orchestrator
│   ├── datadog_retriever.py    # DataDog sub-agent
│   ├── deployment_checker.py   # Deployment checker
│   └── code_checker.py         # Code analyzer
├── utils/                       # Utilities ✅ STRUCTURED
│   ├── datadog_api.py          # DataDog API wrapper
│   ├── github_helper.py        # GitHub helper
│   ├── time_utils.py           # Time utilities
│   └── report_generator.py     # Report generation
└── logs/                        # Application logs
```

## Alternative: Using Traditional venv

If you prefer not to use UV:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Unix/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Troubleshooting

**Issue**: Dependencies not installing
**Solution**: Make sure you have Python 3.9+ installed. Check with `python --version`

**Issue**: API key errors
**Solution**: Make sure `.env` file exists and contains valid API keys

**Issue**: Import errors
**Solution**: Make sure you're running from the project root directory

## Development

To add new dependencies:

```bash
# Add to pyproject.toml under [project.dependencies]
# Then run:
uv sync
```

To update dependencies:

```bash
uv lock --upgrade
```
