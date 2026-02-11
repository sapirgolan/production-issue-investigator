"""
Agent modules for the Production Issue Investigator.

This package contains:
- MainAgent: The main orchestrator agent that coordinates investigation
- DataDogRetriever: Sub-agent for searching and retrieving DataDog logs
- DeploymentChecker: Sub-agent for checking recent deployments (Phase 3)
- CodeChecker: Sub-agent for analyzing code changes (Phase 4)
"""

from agents.main_agent import (
    MainAgent,
    InputMode,
    UserInput,
    ServiceInvestigationResult,
)
from agents.datadog_retriever import (
    DataDogRetriever,
    DataDogSearchInput,
    DataDogSearchResult,
    SearchMode,
    SearchAttempt,
)
from agents.deployment_checker import (
    DeploymentChecker,
    DeploymentInfo,
    DeploymentCheckResult,
)
from agents.code_checker import (
    CodeChecker,
    CodeAnalysisResult,
    FileAnalysis,
    PotentialIssue,
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
]
