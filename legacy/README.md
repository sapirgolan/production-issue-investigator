# Legacy Code - DEPRECATED

This directory contains the pre-SDK implementation of the production issue investigator agents. These files are preserved for rollback capability in case issues are discovered with the new Claude Agent SDK-based implementation.

## Status: DEPRECATED

These files are no longer actively maintained and should not be used for new development.

## Contents

### agents/
Pre-SDK agent implementations:

- **main_agent.py** - Original main orchestrator agent
- **datadog_retriever.py** - Original DataDog log retrieval agent
- **deployment_checker.py** - Original Kubernetes deployment checker agent
- **code_checker.py** - Original code analysis and diff agent
- **exception_analyzer.py** - Original exception analysis agent

### main_legacy.py
Original entry point for the legacy agent system.

## Reason for Deprecation

These implementations were replaced with a new architecture based on the Claude Agent SDK, which provides:

- Better sub-agent orchestration
- Improved error handling and retry logic
- Cleaner separation of concerns
- Native Claude Agent SDK integration

## Rollback Instructions

If you need to rollback to the legacy implementation:

1. Move files from `legacy/agents/` back to `agents/`
2. Move `legacy/main_legacy.py` to the project root
3. Update any imports in dependent files
4. Ensure all dependencies are still available

## Archive Date

Archived: 2026-02-13

## Questions

If you have questions about why these files were deprecated or need assistance with the new implementation, please refer to the main project documentation or contact the development team.
