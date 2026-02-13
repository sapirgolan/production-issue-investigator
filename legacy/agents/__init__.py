"""
Legacy agent modules (deprecated).

These agents have been replaced by the Claude Agent SDK implementation:
- MainAgent -> LeadAgent (agents/lead_agent.py)
- DataDogRetriever -> datadog-investigator subagent
- DeploymentChecker -> deployment-analyzer subagent
- CodeChecker -> code-reviewer subagent
- ExceptionAnalyzer -> Integrated into code-reviewer

See legacy/README.md for rollback instructions.
"""

from legacy.agents.main_agent import (
    MainAgent,
    InputMode,
    UserInput,
    ServiceInvestigationResult,
)
from legacy.agents.datadog_retriever import (
    DataDogRetriever,
    DataDogSearchInput,
    DataDogSearchResult,
    SearchMode,
    SearchAttempt,
)
from legacy.agents.deployment_checker import (
    DeploymentChecker,
    DeploymentInfo,
    DeploymentCheckResult,
)
from legacy.agents.code_checker import (
    CodeChecker,
    CodeAnalysisResult,
    FileAnalysis,
    PotentialIssue,
)
from legacy.agents.exception_analyzer import (
    ExceptionAnalyzer,
    ExceptionAnalysis,
    EXCEPTION_PATTERNS,
)

__all__ = [
    # Main Agent
    "MainAgent",
    "InputMode",
    "UserInput",
    "ServiceInvestigationResult",
    # DataDog Retriever
    "DataDogRetriever",
    "DataDogSearchInput",
    "DataDogSearchResult",
    "SearchMode",
    "SearchAttempt",
    # Deployment Checker
    "DeploymentChecker",
    "DeploymentInfo",
    "DeploymentCheckResult",
    # Code Checker
    "CodeChecker",
    "CodeAnalysisResult",
    "FileAnalysis",
    "PotentialIssue",
    # Exception Analyzer
    "ExceptionAnalyzer",
    "ExceptionAnalysis",
    "EXCEPTION_PATTERNS",
]
