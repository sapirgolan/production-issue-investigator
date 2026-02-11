"""
Report generation utilities for investigation results.

Generates comprehensive markdown reports from investigation data including:
- Executive summary
- Timeline of events
- Root cause analysis
- Evidence (logs, code changes, deployments)
- Proposed fixes
- Next steps for developers
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from utils.logger import get_logger
from utils.time_utils import (
    utc_to_tel_aviv,
    parse_relative_time,
    format_time_range_for_display,
    UTC_TZ,
)

logger = get_logger(__name__)


# Severity indicators for console display
SEVERITY_INDICATORS = {
    "HIGH": "[!!!]",
    "MEDIUM": "[!!]",
    "LOW": "[!]",
}

# Status indicators for report
STATUS_INDICATORS = {
    "success": "[OK]",
    "partial": "[PARTIAL]",
    "error": "[ERROR]",
    "no_deployments": "[NONE]",
    "no_changes": "[NO CHANGES]",
    "not_run": "[SKIPPED]",
}


class ReportGenerator:
    """Generate formatted investigation reports.

    This utility class creates markdown reports from investigation results.
    It aggregates data from DataDog logs, deployment checks, and code analysis
    to produce a comprehensive report with root cause analysis and fix proposals.
    """

    def __init__(self):
        """Initialize the report generator."""
        logger.debug("ReportGenerator initialized")

    def _normalize_service_results(self, service_results_raw: Any) -> List[Dict[str, Any]]:
        """Normalize service_results to a list of dicts.

        Handles both dict and list formats for service_results.

        Args:
            service_results_raw: Either a dict mapping service names to results,
                or a list of service result dicts

        Returns:
            List of service result dictionaries
        """
        if isinstance(service_results_raw, dict):
            # Convert dict to list, adding service_name if not present
            result = []
            for service_name, sr in service_results_raw.items():
                if isinstance(sr, dict):
                    if "service_name" not in sr:
                        sr["service_name"] = service_name
                    result.append(sr)
            return result
        elif isinstance(service_results_raw, list):
            return [sr for sr in service_results_raw if isinstance(sr, dict)]
        else:
            return []

    def generate_report(self, investigation_result: Dict[str, Any]) -> str:
        """Generate a full markdown investigation report.

        Args:
            investigation_result: Dictionary containing:
                - user_input: Dict with mode, log_message/identifiers, datetime
                - datadog_result: Dict with logs, services, efilogids, versions
                - service_results: List of service investigation results
                - search_timestamp: When the investigation was performed

        Returns:
            Markdown-formatted report string
        """
        logger.info("Generating investigation report")

        # Extract key data
        user_input = investigation_result.get("user_input", {})
        datadog_result = investigation_result.get("datadog_result", {})
        service_results_raw = investigation_result.get("service_results", [])
        search_timestamp = investigation_result.get(
            "search_timestamp", datetime.now(UTC_TZ)
        )

        # Normalize service_results to list format
        service_results = self._normalize_service_results(service_results_raw)

        # Store normalized version back into investigation_result for methods that use it
        investigation_result = dict(investigation_result)  # Make a copy
        investigation_result["service_results"] = service_results

        # Determine issue title
        issue_title = self._generate_issue_title(user_input, datadog_result)

        # Determine root cause
        root_cause = self._determine_root_cause(investigation_result)

        # Build report sections
        sections = []

        # Header
        sections.append(self._generate_header(issue_title, user_input, search_timestamp))

        # Executive Summary
        sections.append(self._generate_executive_summary(
            datadog_result, service_results, root_cause
        ))

        # Timeline
        sections.append(self._format_timeline(investigation_result))

        # Services Involved
        sections.append(self._format_services_section(datadog_result, service_results))

        # Root Cause Analysis (enhanced with exception context)
        sections.append(self._format_root_cause_section(root_cause, service_results))

        # Call Flow Analysis (if exception analysis available)
        call_flow_section = self._format_call_flow_section(service_results)
        if call_flow_section:
            sections.append(call_flow_section)

        # Evidence
        sections.append(self._format_evidence(investigation_result))

        # Proposed Fix
        sections.append(self._propose_fix(root_cause, service_results))

        # Testing Required
        sections.append(self._format_testing_section(root_cause, service_results))

        # Files to Modify
        sections.append(self._format_files_to_modify(root_cause, service_results))

        # Next Steps
        sections.append(self._format_next_steps())

        # Investigation Details
        sections.append(self._format_investigation_details(
            datadog_result, service_results, root_cause
        ))

        # Notes
        sections.append(self._format_notes(investigation_result))

        # Footer
        sections.append(self._generate_footer())

        report = "\n".join(sections)
        logger.info(f"Report generated: {len(report)} characters")

        return report

    def _generate_issue_title(
        self,
        user_input: Dict[str, Any],
        datadog_result: Dict[str, Any],
    ) -> str:
        """Generate a brief issue title from the input.

        Args:
            user_input: User input data
            datadog_result: DataDog search results

        Returns:
            Brief issue title string
        """
        mode = user_input.get("mode", "")

        if mode == "LOG_MESSAGE":
            log_message = user_input.get("log_message", "Unknown issue")
            # Truncate and clean the message
            if len(log_message) > 60:
                return log_message[:57] + "..."
            return log_message
        elif mode == "IDENTIFIERS":
            identifiers = user_input.get("identifiers", [])
            services = datadog_result.get("unique_services", [])
            if services:
                return f"Issue in {', '.join(list(services)[:2])}"
            if identifiers:
                return f"Issue for identifiers: {', '.join(identifiers[:2])}"
            return "Production Issue Investigation"
        else:
            return "Production Issue Investigation"

    def _generate_header(
        self,
        issue_title: str,
        user_input: Dict[str, Any],
        search_timestamp: datetime,
    ) -> str:
        """Generate the report header section.

        Args:
            issue_title: Brief title for the issue
            user_input: User input data
            search_timestamp: When investigation was performed

        Returns:
            Header markdown string
        """
        mode = user_input.get("mode", "")

        if mode == "LOG_MESSAGE":
            issue_desc = user_input.get("log_message", "N/A")
        elif mode == "IDENTIFIERS":
            desc = user_input.get("issue_description", "")
            ids = user_input.get("identifiers", [])
            issue_desc = f"{desc} (IDs: {', '.join(ids)})" if desc else f"IDs: {', '.join(ids)}"
        else:
            issue_desc = "N/A"

        # Format timestamp for both UTC and Tel Aviv
        if isinstance(search_timestamp, str):
            search_timestamp = parse_relative_time(search_timestamp)

        utc_time = search_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        tel_aviv_time = utc_to_tel_aviv(search_timestamp).strftime("%Y-%m-%d %H:%M:%S")

        return f"""# Investigation Report: {issue_title}

**Issue**: {issue_desc}
**Investigated**: {utc_time} ({tel_aviv_time} Tel Aviv)
**Status**: PROPOSED FIX (awaiting human review)

---"""

    def _generate_executive_summary(
        self,
        datadog_result: Dict[str, Any],
        service_results: List[Dict[str, Any]],
        root_cause: Dict[str, Any],
    ) -> str:
        """Generate the executive summary section.

        Args:
            datadog_result: DataDog search results
            service_results: List of service investigation results
            root_cause: Determined root cause

        Returns:
            Executive summary markdown string
        """
        logs_count = datadog_result.get("total_logs", 0)
        services = datadog_result.get("unique_services", [])

        # Count deployments and issues
        total_deployments = 0
        total_issues = 0
        for sr in service_results:
            if sr.get("deployment_result"):
                total_deployments += len(sr["deployment_result"].get("deployments", []))
            if sr.get("code_analysis"):
                total_issues += sr["code_analysis"].get("total_issues_found", 0)

        # Build summary based on what we found
        summary_parts = []

        if logs_count > 0:
            summary_parts.append(
                f"Found {logs_count} log entries across {len(services)} service(s)."
            )
        else:
            summary_parts.append("No relevant logs found in the search window.")

        if root_cause.get("identified"):
            confidence = root_cause.get("confidence", "MEDIUM")
            primary_cause = root_cause.get("primary_cause", "Unknown")
            summary_parts.append(
                f"Root cause identified with {confidence} confidence: {primary_cause}"
            )
        elif total_issues > 0:
            summary_parts.append(
                f"Found {total_issues} potential issues in code changes that may be related."
            )
        else:
            summary_parts.append(
                "No definitive root cause identified. Manual review recommended."
            )

        if root_cause.get("fix_available"):
            summary_parts.append("A proposed fix is included below.")

        summary_text = " ".join(summary_parts)

        return f"""## Executive Summary

{summary_text}

---"""

    def _format_timeline(self, investigation_result: Dict[str, Any]) -> str:
        """Format the timeline section.

        Args:
            investigation_result: Full investigation results

        Returns:
            Timeline markdown string
        """
        datadog_result = investigation_result.get("datadog_result", {})
        service_results = investigation_result.get("service_results", [])

        # Get search window
        search_attempts = datadog_result.get("search_attempts", [])
        if search_attempts:
            last_attempt = search_attempts[-1]
            from_time = last_attempt.get("from_time", "N/A")
            to_time = last_attempt.get("to_time", "N/A")
            time_range = format_time_range_for_display(from_time, to_time)
        else:
            time_range = "N/A"

        # Build timeline events
        events = []

        # Add deployment events
        for sr in service_results:
            deployment_result = sr.get("deployment_result", {})
            deployments = deployment_result.get("deployments", [])
            for d in deployments:
                events.append({
                    "timestamp": d.get("deployment_timestamp", "N/A"),
                    "event": "Deployment",
                    "service": sr.get("service_name", "unknown"),
                    "details": f"Commit: {d.get('application_commit_hash', 'N/A')[:8]}",
                })

        # Add error log events (sample)
        logs = datadog_result.get("logs", [])
        error_logs = [l for l in logs if l.get("status") in ("error", "ERROR", "warn", "WARN")]
        for log in error_logs[:5]:  # First 5 error logs
            events.append({
                "timestamp": log.get("timestamp", "N/A"),
                "event": "Error Logged",
                "service": log.get("service", "unknown"),
                "details": (log.get("message", "")[:50] + "...") if log.get("message") else "N/A",
            })

        # Sort events by timestamp
        events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Format table
        table_rows = []
        for event in events[:10]:  # Show first 10 events
            timestamp = event["timestamp"]
            if timestamp and len(timestamp) > 19:
                timestamp = timestamp[:19]
            table_rows.append(
                f"| {timestamp} | {event['event']} | {event['service']} | {event['details']} |"
            )

        if not table_rows:
            table_content = "No timeline events to display."
        else:
            table_content = """| Timestamp | Event | Service | Details |
|-----------|-------|---------|---------|
""" + "\n".join(table_rows)

        return f"""## Timeline

**Log Search Window**: {time_range}
**Deployments Checked**: 72 hours before log search start

{table_content}

---"""

    def _format_services_section(
        self,
        datadog_result: Dict[str, Any],
        service_results: List[Dict[str, Any]],
    ) -> str:
        """Format the services involved section.

        Args:
            datadog_result: DataDog search results
            service_results: List of service investigation results

        Returns:
            Services section markdown string
        """
        services = datadog_result.get("unique_services", [])
        logs = datadog_result.get("logs", [])

        if not services:
            return """## Services Involved

No services identified in the log search.

---"""

        # Count logs per service
        logs_per_service = {}
        for log in logs:
            service = log.get("service", "unknown")
            logs_per_service[service] = logs_per_service.get(service, 0) + 1

        # Build service details
        service_details = []
        for service in sorted(services):
            log_count = logs_per_service.get(service, 0)

            # Find matching service result
            sr = next(
                (s for s in service_results if s.get("service_name") == service),
                {}
            )

            deployment_result = sr.get("deployment_result", {})
            deployments = deployment_result.get("deployments", [])
            deployment_count = len(deployments)

            # Get latest version
            latest_version = "N/A"
            if deployments:
                latest_version = deployments[0].get("dd_version", "N/A")
                if latest_version and len(latest_version) > 20:
                    latest_version = latest_version[:20] + "..."

            service_details.append(f"""**{service}**
   - Logs found: {log_count}
   - Deployments: {deployment_count}
   - Latest version: {latest_version}
""")

        return f"""## Services Involved

{chr(10).join(service_details)}

---"""

    def _determine_root_cause(
        self,
        investigation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze investigation results to determine root cause.

        Args:
            investigation_result: Full investigation results

        Returns:
            Dictionary with root cause analysis:
                - identified: bool
                - confidence: HIGH/MEDIUM/LOW
                - primary_cause: Description
                - service: Service name
                - file_path: File path if known
                - line_number: Line number if known
                - code_snippet: Relevant code
                - contributing_factors: List of other factors
                - fix_available: bool
        """
        root_cause = {
            "identified": False,
            "confidence": "LOW",
            "primary_cause": "Unable to determine root cause from available data",
            "service": None,
            "file_path": None,
            "line_number": None,
            "code_snippet": None,
            "contributing_factors": [],
            "fix_available": False,
        }

        service_results = investigation_result.get("service_results", [])
        datadog_result = investigation_result.get("datadog_result", {})

        # Look for high-severity issues in code analysis
        high_severity_issues = []
        # Handle both dict and list format for service_results
        if isinstance(service_results, dict):
            service_results_list = list(service_results.values())
        else:
            service_results_list = service_results if service_results else []
        for sr in service_results_list:
            if isinstance(sr, str):
                continue  # Skip if it's just a service name string
            if not isinstance(sr, dict):
                continue
            code_analysis = sr.get("code_analysis") or {}
            file_analyses = code_analysis.get("file_analyses", [])

            for fa in file_analyses:
                issues = fa.get("potential_issues", [])
                for issue in issues:
                    if issue.get("severity") == "HIGH":
                        high_severity_issues.append({
                            "service": sr.get("service_name"),
                            "file_path": fa.get("file_path"),
                            "issue": issue,
                            "diff": fa.get("diff"),
                        })

        # If we have high-severity issues, use the first one as primary cause
        if high_severity_issues:
            primary = high_severity_issues[0]
            root_cause["identified"] = True
            root_cause["confidence"] = "HIGH" if len(high_severity_issues) == 1 else "MEDIUM"
            root_cause["primary_cause"] = primary["issue"].get("description", "Code issue detected")
            root_cause["service"] = primary["service"]
            root_cause["file_path"] = primary["file_path"]
            root_cause["code_snippet"] = primary["issue"].get("code_snippet")
            root_cause["fix_available"] = True

            # Add other high-severity issues as contributing factors
            for other in high_severity_issues[1:]:
                root_cause["contributing_factors"].append(
                    f"{other['service']}: {other['issue'].get('description')}"
                )

        # If no high-severity issues, look at medium-severity
        elif service_results_list:
            medium_issues = []
            for sr in service_results_list:
                code_analysis = sr.get("code_analysis", {})
                file_analyses = code_analysis.get("file_analyses", [])

                for fa in file_analyses:
                    issues = fa.get("potential_issues", [])
                    for issue in issues:
                        if issue.get("severity") == "MEDIUM":
                            medium_issues.append({
                                "service": sr.get("service_name"),
                                "file_path": fa.get("file_path"),
                                "issue": issue,
                            })

            if medium_issues:
                primary = medium_issues[0]
                root_cause["identified"] = True
                root_cause["confidence"] = "MEDIUM"
                root_cause["primary_cause"] = primary["issue"].get("description", "Potential code issue")
                root_cause["service"] = primary["service"]
                root_cause["file_path"] = primary["file_path"]
                root_cause["code_snippet"] = primary["issue"].get("code_snippet")
                root_cause["fix_available"] = True

                for other in medium_issues[1:]:
                    root_cause["contributing_factors"].append(
                        f"{other['service']}: {other['issue'].get('description')}"
                    )

        # Check for recent deployments correlation
        for sr in service_results_list:
            deployment_result = sr.get("deployment_result", {})
            deployments = deployment_result.get("deployments", [])

            if deployments and not root_cause["identified"]:
                root_cause["identified"] = True
                root_cause["confidence"] = "LOW"
                root_cause["primary_cause"] = (
                    f"Recent deployment to {sr.get('service_name')} may be related "
                    f"(commit: {deployments[0].get('application_commit_hash', 'N/A')[:8]})"
                )
                root_cause["service"] = sr.get("service_name")
            elif deployments:
                root_cause["contributing_factors"].append(
                    f"Recent deployment to {sr.get('service_name')}"
                )

        logger.debug(f"Root cause analysis: identified={root_cause['identified']}, confidence={root_cause['confidence']}")
        return root_cause

    def _format_root_cause_section(
        self,
        root_cause: Dict[str, Any],
        service_results: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Format the root cause analysis section.

        Args:
            root_cause: Root cause analysis dictionary
            service_results: Service investigation results (for exception context)

        Returns:
            Root cause section markdown string
        """
        # Extract exception context if available
        exception_context = self._extract_exception_context(service_results or [])

        if not root_cause.get("identified"):
            return """## Root Cause Analysis

### Primary Cause
**Confidence**: LOW
**Status**: Unable to determine definitive root cause

The investigation did not identify a clear root cause. This could be because:
- The issue may be related to external dependencies or infrastructure
- The relevant code changes may not be in the analyzed files
- The error may be intermittent or timing-related
- Additional context or investigation may be needed

### Recommended Actions
1. Review the logs manually for additional context
2. Check infrastructure metrics (CPU, memory, network)
3. Verify external service dependencies are healthy
4. Consider enabling additional logging for affected services

---"""

        confidence = root_cause.get("confidence", "MEDIUM")
        service = root_cause.get("service", "Unknown")
        file_path = root_cause.get("file_path", "Unknown")
        primary_cause = root_cause.get("primary_cause", "Unknown")
        code_snippet = root_cause.get("code_snippet", "")

        # Format file location
        location = file_path if file_path else "Unknown"
        if root_cause.get("line_number"):
            location += f":{root_cause['line_number']}"

        # Format code snippet
        snippet_section = ""
        if code_snippet:
            snippet_section = f"""
```diff
{code_snippet}
```
"""

        # Format contributing factors
        contributing_factors = root_cause.get("contributing_factors", [])
        if contributing_factors:
            factors_list = "\n".join([f"- {f}" for f in contributing_factors])
            factors_section = f"""
### Contributing Factors
{factors_list}
"""
        else:
            factors_section = ""

        # Format exception context if available
        exception_section = ""
        if exception_context:
            exc_type = exception_context.get("exception_type", "")
            exc_msg = exception_context.get("exception_message", "")
            if exc_type:
                exception_section = f"\n**Exception**: `{exc_type}`"
                if exc_msg:
                    exception_section += f" - {exc_msg}"
                exception_section += "\n"

        return f"""## Root Cause Analysis

### Primary Cause
**Confidence**: {confidence}
**Service**: {service}
**Location**: `{location}`
{exception_section}
{primary_cause}
{snippet_section}
{factors_section}
---"""

    def _format_evidence(self, investigation_result: Dict[str, Any]) -> str:
        """Format the evidence section.

        Args:
            investigation_result: Full investigation results

        Returns:
            Evidence section markdown string
        """
        datadog_result = investigation_result.get("datadog_result", {})
        service_results = investigation_result.get("service_results", [])

        sections = ["## Evidence\n"]

        # DataDog Logs section
        logs = datadog_result.get("logs", [])
        sections.append("### DataDog Logs\n")

        if not logs:
            sections.append("No relevant logs found.\n")
        else:
            # Show sample of error/warn logs first
            error_logs = [l for l in logs if l.get("status") in ("error", "ERROR", "warn", "WARN")]
            sample_logs = error_logs[:5] if error_logs else logs[:5]

            sections.append("```")
            for log in sample_logs:
                timestamp = log.get("timestamp", "N/A")[:19]
                service = log.get("service", "unknown")
                logger_name = log.get("logger_name", "")
                if logger_name:
                    logger_short = logger_name.split(".")[-1]
                else:
                    logger_short = ""
                message = log.get("message", "")[:100]
                sections.append(f"[{timestamp}] [{service}] [{logger_short}] - {message}")
            sections.append("```\n")

            if len(logs) > 5:
                sections.append(f"*... and {len(logs) - 5} more log entries*\n")

        # Code Changes section
        sections.append("\n### Code Changes\n")

        has_code_changes = False
        for sr in service_results:
            code_analysis = sr.get("code_analysis", {})
            file_analyses = code_analysis.get("file_analyses", [])

            for fa in file_analyses:
                diff = fa.get("diff")
                if diff:
                    has_code_changes = True
                    service_name = sr.get("service_name", "unknown")
                    file_path = fa.get("file_path", "unknown")
                    prev_commit = fa.get("previous_commit", "N/A")[:8]
                    curr_commit = fa.get("current_commit", "N/A")[:8]

                    sections.append(f"**Service**: {service_name}")
                    sections.append(f"**File**: {file_path}")
                    sections.append(f"**Commit**: {prev_commit} -> {curr_commit}\n")

                    # Truncate diff if too long
                    diff_lines = diff.split("\n")
                    if len(diff_lines) > 50:
                        truncated_diff = "\n".join(diff_lines[:50])
                        sections.append("```diff")
                        sections.append(truncated_diff)
                        sections.append("```")
                        sections.append(f"*... diff truncated ({len(diff_lines) - 50} more lines)*\n")
                    else:
                        sections.append("```diff")
                        sections.append(diff)
                        sections.append("```\n")

                    analysis = fa.get("analysis_summary", "")
                    if analysis:
                        sections.append(f"**Analysis**: {analysis}\n")

        if not has_code_changes:
            sections.append("No code changes analyzed or no changes found between versions.\n")

        # Stack Trace Files section
        has_stack_trace_files = False
        for sr in service_results:
            stack_trace_files = sr.get("stack_trace_files", [])
            if stack_trace_files:
                if not has_stack_trace_files:
                    sections.append("\n### Stack Trace Analysis\n")
                    sections.append("Files extracted from stack traces in error logs:\n")
                    has_stack_trace_files = True

                service_name = sr.get("service_name", "unknown")
                sections.append(f"**{service_name}**:")
                for file_path in sorted(stack_trace_files)[:10]:
                    sections.append(f"  - `{file_path}`")
                if len(stack_trace_files) > 10:
                    sections.append(f"  - *... and {len(stack_trace_files) - 10} more files*")
                sections.append("")

        # Deployments section
        sections.append("\n### Deployments\n")

        has_deployments = False
        for sr in service_results:
            deployment_result = sr.get("deployment_result", {})
            deployments = deployment_result.get("deployments", [])

            if deployments:
                has_deployments = True
                service_name = sr.get("service_name", "unknown")
                sections.append(f"**{service_name}**:\n")

                for d in deployments[:3]:  # Show first 3
                    timestamp = d.get("deployment_timestamp", "N/A")
                    commit = d.get("application_commit_hash", "N/A")[:8]
                    build = d.get("build_number", "N/A")
                    pr = d.get("pr_number")

                    pr_str = f" (PR #{pr})" if pr else ""
                    sections.append(f"- {timestamp}: commit {commit}, build {build}{pr_str}")

                if len(deployments) > 3:
                    sections.append(f"- ... and {len(deployments) - 3} more deployments")
                sections.append("")

        if not has_deployments:
            sections.append("No deployments found in the 72-hour window.\n")

        sections.append("\n---")
        return "\n".join(sections)

    def _propose_fix(
        self,
        root_cause: Dict[str, Any],
        service_results: List[Dict[str, Any]],
    ) -> str:
        """Generate proposed fix section.

        Args:
            root_cause: Root cause analysis
            service_results: List of service investigation results

        Returns:
            Proposed fix markdown string
        """
        if not root_cause.get("fix_available"):
            return """## Proposed Fix

No specific fix can be proposed based on the available information.

**Recommendations:**
1. Review the logs and code changes manually
2. Add additional logging to understand the issue better
3. Consider rolling back recent deployments if the issue is critical
4. Engage the team for manual root cause analysis

---"""

        service = root_cause.get("service", "unknown-service")
        file_path = root_cause.get("file_path", "unknown")
        primary_cause = root_cause.get("primary_cause", "")

        # Determine fix based on issue type
        fix_options = []

        if "error handling" in primary_cause.lower():
            fix_options.append({
                "name": "Add Error Handling",
                "risk": "LOW",
                "description": "Restore or improve error handling around the affected code",
                "code": """try {
    // Original code here
} catch (e: Exception) {
    logger.error("Error in operation: ${e.message}", e)
    // Handle gracefully or rethrow with context
    throw ServiceException("Operation failed", e)
}""",
                "why": "Proper error handling prevents exceptions from propagating unexpectedly and provides better debugging information.",
            })

        if "exception" in primary_cause.lower() or "throw" in primary_cause.lower():
            fix_options.append({
                "name": "Handle Exception Gracefully",
                "risk": "MEDIUM",
                "description": "Add proper exception handling or validation before the throwing code",
                "code": """// Add validation before operation
if (condition == null) {
    logger.warn("Condition not met, returning default")
    return defaultValue
}

// Original code with exception
doOperation(condition)""",
                "why": "Validation before operations prevents exceptions from being thrown in expected edge cases.",
            })

        if "database" in primary_cause.lower() or "sql" in primary_cause.lower():
            fix_options.append({
                "name": "Fix Database Query",
                "risk": "MEDIUM",
                "description": "Review and fix the database query or add proper transaction handling",
                "code": """@Transactional(readOnly = true)
fun findData(id: Long): Data? {
    return repository.findById(id)
        .orElse(null)  // Return null instead of throwing
}""",
                "why": "Proper transaction boundaries and null handling prevent database-related exceptions.",
            })

        if "api" in primary_cause.lower() or "http" in primary_cause.lower():
            fix_options.append({
                "name": "Add API Error Handling",
                "risk": "LOW",
                "description": "Add retry logic and proper error handling for external API calls",
                "code": """private fun callExternalApi(): Response {
    return try {
        webClient.get()
            .uri(apiUrl)
            .retrieve()
            .bodyToMono(Response::class.java)
            .timeout(Duration.ofSeconds(30))
            .block()
    } catch (e: WebClientException) {
        logger.error("API call failed: ${e.message}")
        Response.error()  // Return safe default
    }
}""",
                "why": "External API calls can fail for various reasons. Proper timeout and error handling prevents cascading failures.",
            })

        if "async" in primary_cause.lower() or "timing" in primary_cause.lower():
            fix_options.append({
                "name": "Fix Async/Timing Issue",
                "risk": "HIGH",
                "description": "Review async code for race conditions or timing issues",
                "code": """// Ensure proper synchronization
private val mutex = Mutex()

suspend fun processAsync(data: Data) {
    mutex.withLock {
        // Critical section
        doProcessing(data)
    }
}""",
                "why": "Async code needs proper synchronization to prevent race conditions.",
            })

        # Default fix if nothing specific matched
        if not fix_options:
            fix_options.append({
                "name": "Review and Fix Code",
                "risk": "MEDIUM",
                "description": "Review the identified code changes and apply appropriate fix",
                "code": root_cause.get("code_snippet", "// Review the code changes in the diff above"),
                "why": "The specific fix depends on the exact nature of the issue. Review the code changes and apply the appropriate correction.",
            })

        # Format fix options
        sections = ["## Proposed Fix\n"]

        for i, fix in enumerate(fix_options):
            recommended = " (Recommended)" if i == 0 else ""
            sections.append(f"### Option {chr(65 + i)}: {fix['name']}{recommended}")
            sections.append(f"**Risk**: {fix['risk']}")
            sections.append(f"**Scope**: `{file_path}`\n")
            sections.append(f"{fix['description']}\n")
            code = fix.get('code') or "// Review the code changes"
            sections.append("```kotlin")
            sections.append(code)
            sections.append("```\n")
            why = fix.get('why') or "Review the specific issue and apply the appropriate fix."
            sections.append(f"**Why this works**: {why}\n")

        sections.append("---")
        return "\n".join(sections)

    def _format_testing_section(
        self,
        root_cause: Dict[str, Any],
        service_results: List[Dict[str, Any]],
    ) -> str:
        """Format the testing requirements section.

        Args:
            root_cause: Root cause analysis
            service_results: Service investigation results

        Returns:
            Testing section markdown string
        """
        service = root_cause.get("service", "the affected service")

        return f"""## Testing Required

### Manual Tests
1. [ ] Reproduce the original error scenario
2. [ ] Verify the fix resolves the issue without side effects
3. [ ] Test edge cases (null values, empty collections, timeouts)
4. [ ] Verify logging is appropriate (not too verbose, captures errors)
5. [ ] Test with production-like data volume

### Automated Tests Needed
1. [ ] Unit test for the fixed method/class
2. [ ] Integration test covering the error scenario
3. [ ] Add regression test to prevent future occurrences
4. [ ] Consider adding contract tests for external dependencies

### Monitoring After Deployment
1. [ ] Watch {service} error rates for 24 hours
2. [ ] Monitor related services for cascading effects
3. [ ] Set up alert if error recurs

---"""

    def _format_files_to_modify(
        self,
        root_cause: Dict[str, Any],
        service_results: List[Dict[str, Any]],
    ) -> str:
        """Format the files to modify section.

        Args:
            root_cause: Root cause analysis
            service_results: Service investigation results

        Returns:
            Files to modify markdown string
        """
        files = []

        # Add file from root cause
        if root_cause.get("file_path"):
            files.append({
                "path": root_cause["file_path"],
                "change": "Apply fix for " + root_cause.get("primary_cause", "identified issue")[:50],
            })

        # Add files from code analysis with issues
        for sr in service_results:
            code_analysis = sr.get("code_analysis", {})
            for fa in code_analysis.get("file_analyses", []):
                if fa.get("potential_issues"):
                    file_path = fa.get("file_path", "")
                    if file_path and not any(f["path"] == file_path for f in files):
                        files.append({
                            "path": file_path,
                            "change": "Review potential issues identified in analysis",
                        })

        if not files:
            return """## Files to Modify

Unable to identify specific files to modify. Review the code changes and logs manually.

---"""

        file_list = "\n".join([f"{i+1}. `{f['path']}` - {f['change']}" for i, f in enumerate(files)])

        return f"""## Files to Modify

{file_list}

---"""

    def _format_next_steps(self) -> str:
        """Format the next steps section.

        Returns:
            Next steps markdown string
        """
        return """## Next Steps for Developer

1. [ ] Review this report thoroughly
2. [ ] Verify root cause hypothesis matches your understanding
3. [ ] Implement proposed fix (or alternative solution)
4. [ ] Write/update unit tests
5. [ ] Test locally with similar scenarios
6. [ ] Create PR with fix and link to this investigation
7. [ ] Request code review
8. [ ] Deploy to staging and verify fix
9. [ ] Deploy to production
10. [ ] Monitor for 24 hours for recurrence

---"""

    def _format_investigation_details(
        self,
        datadog_result: Dict[str, Any],
        service_results: List[Dict[str, Any]],
        root_cause: Dict[str, Any],
    ) -> str:
        """Format the investigation details section.

        Args:
            datadog_result: DataDog search results
            service_results: Service investigation results
            root_cause: Root cause analysis

        Returns:
            Investigation details markdown string
        """
        # DataDog stats
        dd_attempts = len(datadog_result.get("search_attempts", []))
        dd_logs = datadog_result.get("total_logs", 0)
        dd_services = datadog_result.get("unique_services", [])
        dd_status = "Success" if dd_logs > 0 else "No logs found"

        # Deployment stats
        deploy_services = [sr.get("service_name") for sr in service_results if sr.get("deployment_result")]
        deploy_count = sum(
            len(sr.get("deployment_result", {}).get("deployments", []))
            for sr in service_results
        )
        deploy_status = "Success" if deploy_count > 0 else "No deployments found"

        # Code analysis stats
        code_files = sum(
            sr.get("code_analysis", {}).get("files_analyzed", 0)
            for sr in service_results
        )
        code_diffs = sum(
            1 for sr in service_results
            for fa in sr.get("code_analysis", {}).get("file_analyses", [])
            if fa.get("diff")
        )
        code_status = "Success" if code_files > 0 else "No files analyzed"

        return f"""## Investigation Details

### Sub-Agent Results

**DataDog Information Retriever**:
- Query attempts: {dd_attempts}
- Logs found: {dd_logs}
- Services identified: {', '.join(dd_services) if dd_services else 'None'}
- Status: {dd_status}

**Deployment Checker**:
- Services checked: {', '.join(deploy_services) if deploy_services else 'None'}
- Deployments found: {deploy_count}
- Status: {deploy_status}

**Code Checker**:
- Files analyzed: {code_files}
- Diffs generated: {code_diffs}
- Status: {code_status}

---"""

    def _format_notes(self, investigation_result: Dict[str, Any]) -> str:
        """Format the notes section.

        Args:
            investigation_result: Full investigation results

        Returns:
            Notes markdown string
        """
        notes = []

        # Check for partial results
        service_results = investigation_result.get("service_results", [])
        for sr in service_results:
            if sr.get("error"):
                notes.append(f"- Error investigating {sr.get('service_name')}: {sr.get('error')}")

            code_analysis = sr.get("code_analysis", {})
            if code_analysis.get("status") == "partial":
                notes.append(f"- Code analysis for {sr.get('service_name')} was partial (some files could not be analyzed)")

            if code_analysis.get("error"):
                notes.append(f"- Code analysis error for {sr.get('service_name')}: {code_analysis.get('error')}")

        # Check for warnings
        datadog_result = investigation_result.get("datadog_result", {})
        if datadog_result.get("efilogids_found", 0) > datadog_result.get("efilogids_processed", 0):
            notes.append(
                f"- Only {datadog_result.get('efilogids_processed')} of "
                f"{datadog_result.get('efilogids_found')} sessions were fully analyzed"
            )

        if not notes:
            notes.append("- Investigation completed without warnings")

        notes_text = "\n".join(notes)

        return f"""## Notes

{notes_text}

---"""

    def _extract_exception_context(
        self,
        service_results: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Extract exception analysis context from service results.

        Args:
            service_results: Service investigation results

        Returns:
            Exception context dict or None
        """
        for sr in service_results:
            exception_analysis = sr.get("exception_analysis")
            if exception_analysis:
                return {
                    "exception_type": exception_analysis.get("exception_type"),
                    "exception_message": exception_analysis.get("exception_message"),
                    "root_cause_explanation": exception_analysis.get("root_cause_explanation"),
                    "call_flow": exception_analysis.get("call_flow", []),
                    "suggested_fixes": exception_analysis.get("suggested_fixes", []),
                    "service": sr.get("service_name"),
                }
        return None

    def _format_call_flow_section(
        self,
        service_results: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Format the call flow analysis section.

        Shows the stack trace call flow with changed status for each frame.

        Args:
            service_results: Service investigation results

        Returns:
            Call flow section markdown string, or None if no call flow
        """
        # Find first service with exception analysis and call flow
        exception_context = self._extract_exception_context(service_results)
        if not exception_context:
            return None

        call_flow = exception_context.get("call_flow", [])
        if not call_flow:
            return None

        exception_type = exception_context.get("exception_type", "Exception")
        exception_message = exception_context.get("exception_message", "")

        sections = ["## Call Flow Analysis\n"]

        # Exception header
        if exception_message:
            sections.append(f"**Exception**: `{exception_type}`: {exception_message}\n")
        else:
            sections.append(f"**Exception**: `{exception_type}`\n")

        # Build call flow table
        sections.append("| Step | Class | Method | Line | Changed |")
        sections.append("|------|-------|--------|------|---------|")

        for step in call_flow:
            step_num = step.get("step_number", "?")
            class_name = step.get("class_name", "Unknown")
            # Shorten class name
            class_short = class_name.split(".")[-1] if class_name else "?"
            method_name = step.get("method_name", "?")
            line_number = step.get("line_number", "?")

            # Determine changed status
            is_changed = step.get("is_changed", False)
            is_root_cause = step.get("is_root_cause", False)

            changed_marker = ""
            if is_changed:
                changed_marker = "**YES** "
            if is_root_cause:
                changed_marker += "[ROOT]"

            if not changed_marker:
                changed_marker = "No"

            sections.append(
                f"| {step_num} | `{class_short}` | `{method_name}()` | {line_number} | {changed_marker} |"
            )

        # Add explanation if available
        explanation = exception_context.get("root_cause_explanation")
        if explanation:
            sections.append(f"\n**Analysis**: {explanation}\n")

        sections.append("\n---")
        return "\n".join(sections)

    def _generate_footer(self) -> str:
        """Generate the report footer.

        Returns:
            Footer markdown string
        """
        return """*Generated by Production Issue Investigator Agent*
"""


def generate_report(investigation_result: Dict[str, Any]) -> str:
    """Convenience function to generate a report.

    Args:
        investigation_result: Full investigation results

    Returns:
        Markdown report string
    """
    generator = ReportGenerator()
    return generator.generate_report(investigation_result)
