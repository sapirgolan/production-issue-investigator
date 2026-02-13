/**
 * @process claude-agent-sdk-rewrite
 * @description Rewrite Production Issue Investigator to use Claude Agent SDK
 * @inputs { targetQuality: number, skipToPhase: number }
 * @outputs { success: boolean, phases: array, finalQuality: number }
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * Claude Agent SDK Rewrite Process
 *
 * Implements the REWRITE_PLAN.md with 6 phases:
 * - Phase 1: Foundation Setup (session management, hooks)
 * - Phase 2: Custom MCP Tools (DataDog, GitHub)
 * - Phase 3: Subagent Definitions (prompts, AgentDefinition)
 * - Phase 4: Lead Agent Implementation
 * - Phase 5: Testing & Refinement
 * - Phase 6: Production Deployment
 *
 * Uses TDD approach with quality gates at each phase.
 */
export async function process(inputs, ctx) {
  const { targetQuality = 85, skipToPhase = 1 } = inputs;
  const phaseResults = [];

  // ============================================================================
  // PHASE 1: FOUNDATION SETUP
  // ============================================================================

  if (skipToPhase <= 1) {
    const phase1Result = await runPhase1(ctx, targetQuality);
    phaseResults.push({ phase: 1, name: 'Foundation Setup', ...phase1Result });

    // Phase 1 Gate Breakpoint
    await ctx.breakpoint({
      question: `Phase 1 (Foundation Setup) complete. Quality: ${phase1Result.quality}%. Gate criteria met: ${phase1Result.gatePassed}. Review deliverables and approve to proceed to Phase 2?`,
      title: 'Phase 1 Gate Review',
      context: {
        runId: ctx.runId,
        files: [
          { path: 'utils/session_manager.py', format: 'python', label: 'Session Manager' },
          { path: 'utils/hooks.py', format: 'python', label: 'Hooks' },
          { path: 'tests/test_session_manager.py', format: 'python', label: 'Session Tests' },
          { path: 'tests/test_hooks.py', format: 'python', label: 'Hooks Tests' }
        ]
      }
    });
  }

  // ============================================================================
  // PHASE 2: CUSTOM MCP TOOLS
  // ============================================================================

  if (skipToPhase <= 2) {
    const phase2Result = await runPhase2(ctx, targetQuality);
    phaseResults.push({ phase: 2, name: 'Custom MCP Tools', ...phase2Result });

    // Phase 2 Gate Breakpoint
    await ctx.breakpoint({
      question: `Phase 2 (Custom MCP Tools) complete. Quality: ${phase2Result.quality}%. Gate criteria met: ${phase2Result.gatePassed}. Review MCP tools and approve to proceed to Phase 3?`,
      title: 'Phase 2 Gate Review',
      context: {
        runId: ctx.runId,
        files: [
          { path: 'mcp_servers/datadog_server.py', format: 'python', label: 'DataDog MCP' },
          { path: 'mcp_servers/github_server.py', format: 'python', label: 'GitHub MCP' },
          { path: 'tests/test_mcp_tools.py', format: 'python', label: 'MCP Tests' }
        ]
      }
    });
  }

  // ============================================================================
  // PHASE 3: SUBAGENT DEFINITIONS
  // ============================================================================

  if (skipToPhase <= 3) {
    const phase3Result = await runPhase3(ctx, targetQuality);
    phaseResults.push({ phase: 3, name: 'Subagent Definitions', ...phase3Result });

    // Phase 3 Gate Breakpoint - CRITICAL
    await ctx.breakpoint({
      question: `Phase 3 (Subagent Definitions) complete. This is a CRITICAL gate. Subagent quality directly impacts final report quality. Review prompts and AgentDefinitions. Approve to proceed to Phase 4?`,
      title: 'Phase 3 CRITICAL Gate Review',
      context: {
        runId: ctx.runId,
        files: [
          { path: 'agents/datadog_investigator_prompt.py', format: 'python', label: 'DataDog Investigator' },
          { path: 'agents/deployment_analyzer_prompt.py', format: 'python', label: 'Deployment Analyzer' },
          { path: 'agents/code_reviewer_prompt.py', format: 'python', label: 'Code Reviewer' },
          { path: 'agents/subagent_definitions.py', format: 'python', label: 'AgentDefinitions' }
        ]
      }
    });
  }

  // ============================================================================
  // PHASE 4: LEAD AGENT IMPLEMENTATION
  // ============================================================================

  if (skipToPhase <= 4) {
    const phase4Result = await runPhase4(ctx, targetQuality);
    phaseResults.push({ phase: 4, name: 'Lead Agent Implementation', ...phase4Result });

    // Phase 4 Gate Breakpoint
    await ctx.breakpoint({
      question: `Phase 4 (Lead Agent) complete. Quality: ${phase4Result.quality}%. Integration tests: ${phase4Result.integrationPassed ? 'PASSED' : 'FAILED'}. Review lead agent and approve to proceed to Phase 5?`,
      title: 'Phase 4 Gate Review',
      context: {
        runId: ctx.runId,
        files: [
          { path: 'agents/lead_agent.py', format: 'python', label: 'Lead Agent' },
          { path: 'main.py', format: 'python', label: 'Entry Point' },
          { path: 'tests/test_lead_agent_integration.py', format: 'python', label: 'Integration Tests' }
        ]
      }
    });
  }

  // ============================================================================
  // PHASE 5: TESTING & REFINEMENT
  // ============================================================================

  if (skipToPhase <= 5) {
    const phase5Result = await runPhase5(ctx, targetQuality);
    phaseResults.push({ phase: 5, name: 'Testing & Refinement', ...phase5Result });

    // Phase 5 Gate Breakpoint - FINAL QUALITY GATE
    await ctx.breakpoint({
      question: `Phase 5 (Testing) complete. FINAL QUALITY GATE. Overall coverage: ${phase5Result.overallCoverage}%. Critical path coverage: ${phase5Result.criticalPathCoverage}%. Total tests: ${phase5Result.totalTests}. Approve to proceed to Phase 6 (Production)?`,
      title: 'Phase 5 FINAL Quality Gate',
      context: {
        runId: ctx.runId,
        files: [
          { path: 'coverage_report.html', format: 'html', label: 'Coverage Report' }
        ]
      }
    });
  }

  // ============================================================================
  // PHASE 6: PRODUCTION DEPLOYMENT
  // ============================================================================

  if (skipToPhase <= 6) {
    const phase6Result = await runPhase6(ctx, targetQuality);
    phaseResults.push({ phase: 6, name: 'Production Deployment', ...phase6Result });

    // Final approval
    await ctx.breakpoint({
      question: `Phase 6 (Production) complete! Security review: ${phase6Result.securityPassed ? 'PASSED' : 'NEEDS ATTENTION'}. Documentation updated: ${phase6Result.docsUpdated}. Ready for production cutover?`,
      title: 'Production Deployment Approval',
      context: {
        runId: ctx.runId,
        files: [
          { path: 'CLAUDE.md', format: 'markdown', label: 'Updated CLAUDE.md' },
          { path: 'README.md', format: 'markdown', label: 'Updated README' }
        ]
      }
    });
  }

  // Calculate final quality
  const totalQuality = phaseResults.reduce((sum, p) => sum + (p.quality || 0), 0) / phaseResults.length;

  return {
    success: phaseResults.every(p => p.gatePassed),
    phases: phaseResults,
    finalQuality: totalQuality,
    targetQuality
  };
}

// ============================================================================
// PHASE 1: FOUNDATION SETUP
// ============================================================================

async function runPhase1(ctx, targetQuality) {
  // Step 1: Write tests first (TDD)
  const testResult = await ctx.task(writePhase1TestsTask, {
    targetQuality,
    components: ['session_manager', 'hooks', 'config']
  });

  // Step 2: Implement session manager
  const sessionResult = await ctx.task(implementSessionManagerTask, {
    testResult
  });

  // Step 3: Implement hooks
  const hooksResult = await ctx.task(implementHooksTask, {
    testResult
  });

  // Step 4: Update config
  const configResult = await ctx.task(updateConfigTask, {
    testResult
  });

  // Step 5: Create directory structure
  const dirResult = await ctx.task(createDirectoryStructureTask, {});

  // Step 6: Quality check
  const qualityResult = await ctx.task(runPhase1QualityCheckTask, {
    targetQuality,
    testFiles: ['tests/test_session_manager.py', 'tests/test_hooks.py'],
    targetCoverage: 95
  });

  return {
    quality: qualityResult.qualityScore,
    gatePassed: qualityResult.qualityScore >= targetQuality,
    testCount: qualityResult.testCount,
    coverage: qualityResult.coverage,
    sessionManager: sessionResult,
    hooks: hooksResult,
    config: configResult
  };
}

// ============================================================================
// PHASE 2: CUSTOM MCP TOOLS
// ============================================================================

async function runPhase2(ctx, targetQuality) {
  // Step 1: Write MCP tool tests first (TDD)
  const testResult = await ctx.task(writeMCPToolTestsTask, {
    targetQuality,
    tools: ['search_logs', 'get_logs_by_efilogid', 'parse_stack_trace',
            'search_commits', 'get_file_content', 'get_pr_files', 'compare_commits']
  });

  // Step 2: Implement DataDog MCP server
  const datadogResult = await ctx.task(implementDataDogMCPTask, {
    testResult
  });

  // Step 3: Implement GitHub MCP server
  const githubResult = await ctx.task(implementGitHubMCPTask, {
    testResult
  });

  // Step 4: Quality check
  const qualityResult = await ctx.task(runPhase2QualityCheckTask, {
    targetQuality,
    targetCoverage: 95
  });

  return {
    quality: qualityResult.qualityScore,
    gatePassed: qualityResult.qualityScore >= targetQuality && qualityResult.testCount >= 20,
    testCount: qualityResult.testCount,
    coverage: qualityResult.coverage,
    datadog: datadogResult,
    github: githubResult
  };
}

// ============================================================================
// PHASE 3: SUBAGENT DEFINITIONS
// ============================================================================

async function runPhase3(ctx, targetQuality) {
  // Step 1: Create DataDog Investigator prompt
  const datadogInvestigatorResult = await ctx.task(createDataDogInvestigatorTask, {});

  // Step 2: Create Deployment Analyzer prompt
  const deploymentAnalyzerResult = await ctx.task(createDeploymentAnalyzerTask, {});

  // Step 3: Create Code Reviewer prompt
  const codeReviewerResult = await ctx.task(createCodeReviewerTask, {});

  // Step 4: Create subagent definitions file
  const definitionsResult = await ctx.task(createSubagentDefinitionsTask, {
    datadogInvestigator: datadogInvestigatorResult,
    deploymentAnalyzer: deploymentAnalyzerResult,
    codeReviewer: codeReviewerResult
  });

  // Step 5: Manual validation (this is primarily a prompt quality phase)
  const validationResult = await ctx.task(validateSubagentPromptsTask, {
    datadogInvestigator: datadogInvestigatorResult,
    deploymentAnalyzer: deploymentAnalyzerResult,
    codeReviewer: codeReviewerResult
  });

  return {
    quality: validationResult.qualityScore,
    gatePassed: validationResult.allValid,
    datadogInvestigator: datadogInvestigatorResult,
    deploymentAnalyzer: deploymentAnalyzerResult,
    codeReviewer: codeReviewerResult,
    definitions: definitionsResult
  };
}

// ============================================================================
// PHASE 4: LEAD AGENT IMPLEMENTATION
// ============================================================================

async function runPhase4(ctx, targetQuality) {
  // Step 1: Write lead agent tests (TDD)
  const testResult = await ctx.task(writeLeadAgentTestsTask, {
    targetQuality
  });

  // Step 2: Implement lead agent
  const leadAgentResult = await ctx.task(implementLeadAgentTask, {
    testResult
  });

  // Step 3: Update main.py entry point
  const mainResult = await ctx.task(updateMainEntryPointTask, {
    leadAgentResult
  });

  // Step 4: Integration tests
  const integrationResult = await ctx.task(runLeadAgentIntegrationTestsTask, {
    targetQuality
  });

  // Step 5: Quality check
  const qualityResult = await ctx.task(runPhase4QualityCheckTask, {
    targetQuality,
    targetCoverage: 95
  });

  return {
    quality: qualityResult.qualityScore,
    gatePassed: qualityResult.qualityScore >= targetQuality && integrationResult.passed,
    integrationPassed: integrationResult.passed,
    testCount: qualityResult.testCount,
    coverage: qualityResult.coverage,
    leadAgent: leadAgentResult
  };
}

// ============================================================================
// PHASE 5: TESTING & REFINEMENT
// ============================================================================

async function runPhase5(ctx, targetQuality) {
  let iteration = 0;
  let currentQuality = 0;
  let converged = false;
  const maxIterations = 5;
  const results = [];

  while (iteration < maxIterations && !converged) {
    iteration++;

    // Step 1: Run all tests
    const testRunResult = await ctx.task(runAllTestsTask, {
      iteration
    });

    // Step 2: Check coverage
    const coverageResult = await ctx.task(checkCoverageTask, {
      iteration,
      criticalPaths: [
        'mcp_servers/datadog_server.py',
        'mcp_servers/github_server.py',
        'utils/session_manager.py',
        'utils/hooks.py',
        'agents/lead_agent.py'
      ],
      targetCriticalCoverage: 95,
      targetOverallCoverage: 85
    });

    currentQuality = coverageResult.overallCoverage;

    results.push({
      iteration,
      testsPassed: testRunResult.passed,
      totalTests: testRunResult.total,
      overallCoverage: coverageResult.overallCoverage,
      criticalPathCoverage: coverageResult.criticalPathCoverage
    });

    if (coverageResult.overallCoverage >= 85 && coverageResult.criticalPathCoverage >= 95 && testRunResult.passed) {
      converged = true;
    } else if (iteration < maxIterations) {
      // Add more tests/fix issues
      await ctx.task(refineTestsAndCoverageTask, {
        iteration,
        coverageGaps: coverageResult.gaps,
        failingTests: testRunResult.failures
      });
    }
  }

  // Comparison test with legacy
  const comparisonResult = await ctx.task(comparisonTestTask, {
    testCases: 3
  });

  return {
    quality: currentQuality,
    gatePassed: converged && comparisonResult.equivalent,
    overallCoverage: results[results.length - 1]?.overallCoverage || 0,
    criticalPathCoverage: results[results.length - 1]?.criticalPathCoverage || 0,
    totalTests: results[results.length - 1]?.totalTests || 0,
    iterations: iteration,
    comparisonPassed: comparisonResult.equivalent
  };
}

// ============================================================================
// PHASE 6: PRODUCTION DEPLOYMENT
// ============================================================================

async function runPhase6(ctx, targetQuality) {
  // Step 1: Security review
  const securityResult = await ctx.task(securityReviewTask, {});

  // Step 2: Update documentation
  const docsResult = await ctx.task(updateDocumentationTask, {});

  // Step 3: Move legacy code
  const legacyResult = await ctx.task(moveLegacyCodeTask, {});

  // Step 4: Production smoke tests
  const smokeTestResult = await ctx.task(productionSmokeTestTask, {
    testCount: 5
  });

  return {
    quality: smokeTestResult.successRate,
    gatePassed: securityResult.passed && smokeTestResult.allPassed,
    securityPassed: securityResult.passed,
    docsUpdated: docsResult.updated,
    legacyMoved: legacyResult.moved,
    smokeTestsPassed: smokeTestResult.allPassed
  };
}

// ============================================================================
// TASK DEFINITIONS - PHASE 1
// ============================================================================

export const writePhase1TestsTask = defineTask('write-phase1-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Write Phase 1 tests (TDD)',
  description: 'Write tests for session manager and hooks before implementation',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python test engineer specializing in TDD',
      task: 'Write comprehensive tests for Phase 1 components: session manager and hooks',
      context: {
        components: args.components,
        targetQuality: args.targetQuality,
        existingTestPattern: 'tests/test_*.py',
        testFramework: 'pytest',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for Phase 1 requirements',
        'Create tests/test_session_manager.py with tests for:',
        '  - Session directory creation (logs/session_YYYYMMDD_HHMMSS/)',
        '  - Transcript writing (append-only)',
        '  - Tool call JSONL logging',
        '  - Session ID generation',
        '  - Subdirectory creation (files/datadog_findings/, etc.)',
        'Create tests/test_hooks.py with tests for:',
        '  - SubagentTracker initialization',
        '  - PreToolUse hook logging (tool_name, input, parent_tool_use_id)',
        '  - PostToolUse hook logging (success, duration, output_size)',
        '  - Parent-child tool call relationship tracking',
        '  - JSONL file writing',
        '  - Transcript file writing',
        'Follow existing test patterns in tests/ directory',
        'Use pytest fixtures and mocking',
        'Target 8+ tests minimum',
        'Tests should fail initially (TDD red phase)',
        'Return summary of tests created'
      ],
      outputFormat: 'JSON with testsCreated (array), testCount (number), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['testsCreated', 'testCount', 'summary'],
      properties: {
        testsCreated: { type: 'array', items: { type: 'string' } },
        testCount: { type: 'number' },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase1', 'tdd', 'testing']
}));

export const implementSessionManagerTask = defineTask('implement-session-manager', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement session manager',
  description: 'Implement utils/session_manager.py to make tests pass',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Implement session manager following TDD - make all tests pass',
      context: {
        testResult: args.testResult,
        targetFile: 'utils/session_manager.py',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for SessionManager specification',
        'Create utils/session_manager.py following the code example in the plan',
        'Implement SessionManager class with:',
        '  - __init__(self, logs_dir: Optional[Path] = None)',
        '  - create_session(self) -> Path',
        '  - write_transcript(self, text: str, end: str = "") -> None',
        '  - get_findings_dir(self, subagent: str) -> Path',
        'Create session directories: logs/session_YYYYMMDD_HHMMSS/',
        'Create subdirectories: files/datadog_findings/, files/deployment_findings/, files/code_findings/',
        'Make all tests in tests/test_session_manager.py pass',
        'Follow existing code patterns in utils/',
        'Return summary of implementation'
      ],
      outputFormat: 'JSON with filesCreated (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase1', 'implementation']
}));

export const implementHooksTask = defineTask('implement-hooks', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement hooks system',
  description: 'Implement utils/hooks.py for tool usage tracking',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer familiar with Claude Agent SDK',
      task: 'Implement hooks system for tracking tool usage across agents',
      context: {
        testResult: args.testResult,
        targetFile: 'utils/hooks.py',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for SubagentTracker specification',
        'Read the Claude Agent SDK hook patterns from Context7 documentation',
        'Create utils/hooks.py following the code example in the plan',
        'Implement SubagentTracker class with:',
        '  - __init__(self, log_file: Path, transcript_file: Path)',
        '  - async pre_tool_use_hook(self, input_data, tool_use_id, context) -> dict',
        '  - async post_tool_use_hook(self, input_data, tool_use_id, context) -> dict',
        '  - _truncate_input(self, tool_input, max_size=500) -> dict',
        '  - _extract_error(self, tool_response) -> str',
        '  - _write_jsonl(self, entry) -> None',
        '  - _write_transcript(self, text) -> None',
        '  - close(self) -> None',
        'Implement create_hook_matchers(tracker) function',
        'Track parent-child tool call relationships via parent_tool_use_id',
        'Log tool calls to JSONL with timestamps and durations',
        'Make all tests in tests/test_hooks.py pass',
        'Return summary of implementation'
      ],
      outputFormat: 'JSON with filesCreated (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase1', 'implementation']
}));

export const updateConfigTask = defineTask('update-config', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update config system',
  description: 'Add per-agent model configuration to utils/config.py',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Update config system with per-agent model configuration',
      context: {
        testResult: args.testResult,
        targetFile: 'utils/config.py',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read existing utils/config.py to understand current patterns',
        'Read docs/REWRITE_PLAN.md for config requirements',
        'Add the following configuration options:',
        '  - session_log_dir (default: "logs")',
        '  - bypass_permissions flag (default from PERMISSION_MODE env)',
        '  - LEAD_AGENT_MODEL (default: opus)',
        '  - DATADOG_INVESTIGATOR_MODEL (default: haiku)',
        '  - DEPLOYMENT_ANALYZER_MODEL (default: haiku)',
        '  - CODE_REVIEWER_MODEL (default: sonnet)',
        '  - TOOL_ERROR_RETRIES (default: 1)',
        '  - TIMEOUT_RETRIES (default: 0)',
        '  - SCHEMA_ERROR_RETRIES (default: 0)',
        '  - SUBAGENT_TIMEOUT_SECONDS (default: 120)',
        'Follow existing patterns using dataclass or similar',
        'Load values from environment with sensible defaults',
        'Return summary of changes'
      ],
      outputFormat: 'JSON with filesModified (array), changes (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesModified', 'summary'],
      properties: {
        filesModified: { type: 'array', items: { type: 'string' } },
        changes: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase1', 'config']
}));

export const createDirectoryStructureTask = defineTask('create-directory-structure', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create directory structure',
  description: 'Create required directory structure for SDK implementation',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer',
      task: 'Create directory structure for Claude Agent SDK implementation',
      context: {
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Create the following directories if they do not exist:',
        '  - mcp_servers/ (for MCP server implementations)',
        '  - logs/ (for session logs)',
        'Create __init__.py files where needed',
        'Verify existing agents/ and utils/ directories',
        'Return summary of directories created'
      ],
      outputFormat: 'JSON with directoriesCreated (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['directoriesCreated', 'summary'],
      properties: {
        directoriesCreated: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase1', 'setup']
}));

export const runPhase1QualityCheckTask = defineTask('run-phase1-quality-check', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Phase 1 quality check',
  description: 'Run tests and check coverage for Phase 1 components',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer',
      task: 'Run tests and verify Phase 1 quality gate criteria',
      context: {
        targetQuality: args.targetQuality,
        testFiles: args.testFiles,
        targetCoverage: args.targetCoverage,
        testCommand: 'uv run python -m pytest tests/test_session_manager.py tests/test_hooks.py -v',
        coverageCommand: 'uv run python -m pytest tests/test_session_manager.py tests/test_hooks.py --cov=utils/session_manager --cov=utils/hooks --cov-report=term-missing'
      },
      instructions: [
        'Run the test suite for Phase 1 components',
        'Run coverage analysis',
        'Verify gate criteria:',
        '  - 8+ tests pass',
        '  - 95% coverage on session_manager.py and hooks.py',
        'Calculate quality score',
        'Return detailed quality metrics'
      ],
      outputFormat: 'JSON with qualityScore (number), testCount (number), coverage (number), gatePassed (boolean), details (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['qualityScore', 'testCount', 'coverage'],
      properties: {
        qualityScore: { type: 'number' },
        testCount: { type: 'number' },
        coverage: { type: 'number' },
        gatePassed: { type: 'boolean' },
        details: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase1', 'quality']
}));

// ============================================================================
// TASK DEFINITIONS - PHASE 2
// ============================================================================

export const writeMCPToolTestsTask = defineTask('write-mcp-tool-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Write MCP tool tests (TDD)',
  description: 'Write tests for MCP tools before implementation',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python test engineer',
      task: 'Write comprehensive tests for MCP tools (TDD approach)',
      context: {
        tools: args.tools,
        targetQuality: args.targetQuality,
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for MCP tool specifications',
        'Create tests/test_mcp_tools.py with tests for:',
        'DataDog tools:',
        '  - search_logs: successful search, rate limit handling, error handling',
        '  - get_logs_by_efilogid: quote escaping, time window, empty results',
        '  - parse_stack_trace: Kotlin stack traces, Java stack traces, extraction',
        'GitHub tools:',
        '  - search_commits: time range, author filter, pagination',
        '  - get_file_content: specific commit, file not found',
        '  - get_pr_files: PR number, file list',
        '  - compare_commits: diff generation, file path filter',
        'Test error handling for all tools',
        'Test asyncio.to_thread() wrapping',
        'Use mocks for DataDog API and GitHub helper',
        'Target 20+ tests minimum',
        'Return summary of tests'
      ],
      outputFormat: 'JSON with testsCreated (array), testCount (number), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['testsCreated', 'testCount', 'summary'],
      properties: {
        testsCreated: { type: 'array', items: { type: 'string' } },
        testCount: { type: 'number' },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase2', 'tdd', 'testing']
}));

export const implementDataDogMCPTask = defineTask('implement-datadog-mcp', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement DataDog MCP server',
  description: 'Create mcp_servers/datadog_server.py with 3 tools',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer familiar with Claude Agent SDK and MCP',
      task: 'Implement DataDog MCP server with search_logs, get_logs_by_efilogid, and parse_stack_trace tools',
      context: {
        testResult: args.testResult,
        targetFile: 'mcp_servers/datadog_server.py',
        rewritePlan: 'docs/REWRITE_PLAN.md',
        existingUtility: 'utils/datadog_api.py',
        stackTraceParser: 'utils/stack_trace_parser.py'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for DataDog MCP server specification',
        'Read existing utils/datadog_api.py to understand the API wrapper',
        'Read utils/stack_trace_parser.py for stack trace parsing',
        'Create mcp_servers/datadog_server.py following the Claude Agent SDK MCP patterns',
        'Use @tool decorator from claude_agent_sdk',
        'Implement 3 tools:',
        '  1. search_logs: Search DataDog logs with query and time filters',
        '  2. get_logs_by_efilogid: Get all logs for a session ID',
        '  3. parse_stack_trace: Extract file paths and exceptions',
        'Use asyncio.to_thread() to wrap sync calls to datadog_api',
        'Handle rate limits with asyncio.sleep()',
        'Truncate results to avoid context bloat (50 logs max)',
        'Return proper MCP response format with content array',
        'Handle errors and return is_error: true',
        'Create MCP server with create_sdk_mcp_server()',
        'Make all tests pass',
        'Return summary'
      ],
      outputFormat: 'JSON with filesCreated (array), toolsImplemented (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'toolsImplemented', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        toolsImplemented: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase2', 'mcp', 'datadog']
}));

export const implementGitHubMCPTask = defineTask('implement-github-mcp', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement GitHub MCP server',
  description: 'Create mcp_servers/github_server.py with 4 tools',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer familiar with Claude Agent SDK and MCP',
      task: 'Implement GitHub MCP server with search_commits, get_file_content, get_pr_files, and compare_commits tools',
      context: {
        testResult: args.testResult,
        targetFile: 'mcp_servers/github_server.py',
        rewritePlan: 'docs/REWRITE_PLAN.md',
        existingUtility: 'utils/github_helper.py'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for GitHub MCP server specification',
        'Read existing utils/github_helper.py to understand the GitHub helper',
        'Create mcp_servers/github_server.py following Claude Agent SDK MCP patterns',
        'Use @tool decorator from claude_agent_sdk',
        'Implement 4 tools:',
        '  1. search_commits: Search commits in kubernetes or app repos',
        '  2. get_file_content: Get file content at specific commit',
        '  3. get_pr_files: Get changed files in a PR',
        '  4. compare_commits: Get diff between two commits',
        'Use asyncio.to_thread() to wrap sync calls to github_helper',
        'Return proper MCP response format',
        'Handle errors gracefully',
        'Create MCP server with create_sdk_mcp_server()',
        'Make all tests pass',
        'Return summary'
      ],
      outputFormat: 'JSON with filesCreated (array), toolsImplemented (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'toolsImplemented', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        toolsImplemented: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase2', 'mcp', 'github']
}));

export const runPhase2QualityCheckTask = defineTask('run-phase2-quality-check', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Phase 2 quality check',
  description: 'Run tests and check coverage for Phase 2 MCP tools',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer',
      task: 'Run tests and verify Phase 2 quality gate criteria',
      context: {
        targetQuality: args.targetQuality,
        targetCoverage: args.targetCoverage,
        testCommand: 'uv run python -m pytest tests/test_mcp_tools.py -v',
        coverageCommand: 'uv run python -m pytest tests/test_mcp_tools.py --cov=mcp_servers --cov-report=term-missing'
      },
      instructions: [
        'Run the test suite for MCP tools',
        'Run coverage analysis',
        'Verify gate criteria:',
        '  - 20+ tests pass',
        '  - 95% coverage on mcp_servers/',
        '  - All tools functional',
        'Calculate quality score',
        'Return detailed metrics'
      ],
      outputFormat: 'JSON with qualityScore (number), testCount (number), coverage (number), gatePassed (boolean)'
    },
    outputSchema: {
      type: 'object',
      required: ['qualityScore', 'testCount', 'coverage'],
      properties: {
        qualityScore: { type: 'number' },
        testCount: { type: 'number' },
        coverage: { type: 'number' },
        gatePassed: { type: 'boolean' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase2', 'quality']
}));

// ============================================================================
// TASK DEFINITIONS - PHASE 3
// ============================================================================

export const createDataDogInvestigatorTask = defineTask('create-datadog-investigator', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create DataDog Investigator prompt',
  description: 'Create agents/datadog_investigator_prompt.py with comprehensive prompt',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior prompt engineer and SRE specialist',
      task: 'Create the DataDog Investigator subagent prompt following the REWRITE_PLAN.md specification',
      context: {
        targetFile: 'agents/datadog_investigator_prompt.py',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for the DATADOG_INVESTIGATOR_PROMPT specification',
        'Create agents/datadog_investigator_prompt.py',
        'Include comprehensive prompt covering:',
        '  - Role definition (DataDog Log Analysis Expert)',
        '  - Tools available (search_logs, get_logs_by_efilogid, parse_stack_trace, Write, Read)',
        '  - Investigation process for Mode 1 (log message) and Mode 2 (identifiers)',
        '  - Output format (JSON to files/datadog_findings/summary.json)',
        '  - Important notes (UTC timestamps, efilogid escaping, dd.version format)',
        'Follow the exact structure from REWRITE_PLAN.md',
        'Make prompt thorough but focused',
        'Return summary'
      ],
      outputFormat: 'JSON with filesCreated (array), promptLength (number), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'promptLength', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        promptLength: { type: 'number' },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase3', 'subagent', 'prompt']
}));

export const createDeploymentAnalyzerTask = defineTask('create-deployment-analyzer', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create Deployment Analyzer prompt',
  description: 'Create agents/deployment_analyzer_prompt.py with comprehensive prompt',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior prompt engineer and DevOps specialist',
      task: 'Create the Deployment Analyzer subagent prompt following the REWRITE_PLAN.md specification',
      context: {
        targetFile: 'agents/deployment_analyzer_prompt.py',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for the DEPLOYMENT_ANALYZER_PROMPT specification',
        'Create agents/deployment_analyzer_prompt.py',
        'Include comprehensive prompt covering:',
        '  - Role definition (Deployment Correlation Expert)',
        '  - Tools available (search_commits, get_file_content, get_pr_files, Write, Read, Bash)',
        '  - Investigation process (read DataDog findings, search kubernetes commits, correlate)',
        '  - Output format (JSON to files/deployment_findings/)',
        '  - Important notes (kubernetes repo, search window, commit title format)',
        'Follow the exact structure from REWRITE_PLAN.md',
        'Return summary'
      ],
      outputFormat: 'JSON with filesCreated (array), promptLength (number), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'promptLength', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        promptLength: { type: 'number' },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase3', 'subagent', 'prompt']
}));

export const createCodeReviewerTask = defineTask('create-code-reviewer', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create Code Reviewer prompt',
  description: 'Create agents/code_reviewer_prompt.py with comprehensive prompt',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior prompt engineer and code review specialist',
      task: 'Create the Code Reviewer subagent prompt following the REWRITE_PLAN.md specification',
      context: {
        targetFile: 'agents/code_reviewer_prompt.py',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for the CODE_REVIEWER_PROMPT specification',
        'Create agents/code_reviewer_prompt.py',
        'Include comprehensive prompt covering:',
        '  - Role definition (Code Change Analysis Expert)',
        '  - Tools available (get_file_content, compare_commits, Write, Read)',
        '  - Investigation process (read findings, map logger names, get diffs, analyze)',
        '  - Analysis criteria (null safety, exception handling, logic changes, etc.)',
        '  - Severity classification (HIGH, MEDIUM, LOW)',
        '  - Output format (JSON to files/code_findings/)',
        '  - Important notes (service repos, Kotlin null safety, logger name mapping)',
        'Follow the exact structure from REWRITE_PLAN.md',
        'Return summary'
      ],
      outputFormat: 'JSON with filesCreated (array), promptLength (number), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'promptLength', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        promptLength: { type: 'number' },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase3', 'subagent', 'prompt']
}));

export const createSubagentDefinitionsTask = defineTask('create-subagent-definitions', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create subagent definitions',
  description: 'Create agents/subagent_definitions.py with AgentDefinition objects',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer familiar with Claude Agent SDK',
      task: 'Create subagent definitions file with AgentDefinition for each subagent',
      context: {
        targetFile: 'agents/subagent_definitions.py',
        rewritePlan: 'docs/REWRITE_PLAN.md',
        datadogInvestigator: args.datadogInvestigator,
        deploymentAnalyzer: args.deploymentAnalyzer,
        codeReviewer: args.codeReviewer
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for AgentDefinition patterns',
        'Create agents/subagent_definitions.py',
        'Import AgentDefinition from claude_agent_sdk',
        'Import prompts from respective prompt files',
        'Create 3 AgentDefinition objects:',
        '  1. DATADOG_INVESTIGATOR:',
        '     - description: Expert at searching DataDog logs...',
        '     - prompt: from datadog_investigator_prompt.py',
        '     - tools: ["mcp__datadog__search_logs", "mcp__datadog__get_logs_by_efilogid", "mcp__datadog__parse_stack_trace", "Write", "Read", "Glob"]',
        '     - model: haiku (from config or default)',
        '  2. DEPLOYMENT_ANALYZER:',
        '     - description: Expert at finding and analyzing deployments...',
        '     - tools: ["mcp__github__search_commits", "mcp__github__get_file_content", "mcp__github__get_pr_files", "Write", "Read", "Bash"]',
        '     - model: haiku',
        '  3. CODE_REVIEWER:',
        '     - description: Expert at analyzing code changes...',
        '     - tools: ["mcp__github__get_file_content", "mcp__github__compare_commits", "Write", "Read"]',
        '     - model: sonnet',
        'Get model from config with defaults',
        'Return summary'
      ],
      outputFormat: 'JSON with filesCreated (array), definitions (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'definitions', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        definitions: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase3', 'subagent', 'definitions']
}));

export const validateSubagentPromptsTask = defineTask('validate-subagent-prompts', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Validate subagent prompts',
  description: 'Validate prompt quality and completeness',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior prompt engineer and QA specialist',
      task: 'Validate subagent prompts for quality, completeness, and adherence to spec',
      context: {
        datadogInvestigator: args.datadogInvestigator,
        deploymentAnalyzer: args.deploymentAnalyzer,
        codeReviewer: args.codeReviewer,
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read each subagent prompt file',
        'Validate against REWRITE_PLAN.md requirements',
        'Check for:',
        '  - Clear role definition',
        '  - Complete tool descriptions',
        '  - Step-by-step process',
        '  - Exact output format specification',
        '  - Edge case handling',
        '  - Important notes and gotchas',
        'Score each prompt 0-100',
        'Identify any gaps or issues',
        'Return validation results'
      ],
      outputFormat: 'JSON with allValid (boolean), qualityScore (number), scores (object), issues (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['allValid', 'qualityScore'],
      properties: {
        allValid: { type: 'boolean' },
        qualityScore: { type: 'number' },
        scores: { type: 'object' },
        issues: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase3', 'validation']
}));

// ============================================================================
// TASK DEFINITIONS - PHASE 4
// ============================================================================

export const writeLeadAgentTestsTask = defineTask('write-lead-agent-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Write lead agent tests (TDD)',
  description: 'Write tests for lead agent before implementation',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python test engineer',
      task: 'Write comprehensive tests for the lead agent (TDD approach)',
      context: {
        targetQuality: args.targetQuality,
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for lead agent specification',
        'Create tests/test_lead_agent.py with tests for:',
        '  - LeadAgent initialization',
        '  - investigate() method',
        '  - Session management integration',
        '  - Subagent coordination (DataDog -> Deployment -> Code order)',
        '  - Error report generation',
        '  - File-based coordination (reading subagent findings)',
        'Create tests/test_lead_agent_integration.py with:',
        '  - Full workflow with mocked subagents',
        '  - Session directory creation',
        '  - Transcript writing',
        '  - Tool call logging',
        'Use mocks for ClaudeSDKClient and subagents',
        'Target comprehensive coverage',
        'Return summary'
      ],
      outputFormat: 'JSON with testsCreated (array), testCount (number), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['testsCreated', 'testCount', 'summary'],
      properties: {
        testsCreated: { type: 'array', items: { type: 'string' } },
        testCount: { type: 'number' },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase4', 'tdd', 'testing']
}));

export const implementLeadAgentTask = defineTask('implement-lead-agent', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement lead agent',
  description: 'Create agents/lead_agent.py with full SDK integration',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer familiar with Claude Agent SDK',
      task: 'Implement the lead agent following REWRITE_PLAN.md specification',
      context: {
        testResult: args.testResult,
        targetFile: 'agents/lead_agent.py',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for complete LeadAgent specification',
        'Read Claude Agent SDK documentation patterns',
        'Create agents/lead_agent.py following the code example in the plan',
        'Implement LeadAgent class with:',
        '  - __init__(self, config=None)',
        '  - async investigate(self, user_input: str) -> str',
        '  - _generate_error_report(self, user_input: str, error: str) -> str',
        'Implement LEAD_AGENT_PROMPT with comprehensive instructions',
        'Setup session management and hooks',
        'Configure MCP servers (datadog, github)',
        'Define subagent registry',
        'Use query() with ClaudeAgentOptions',
        'Process response stream (AssistantMessage, ResultMessage, etc.)',
        'Implement run_interactive() function',
        'Make all tests pass',
        'Return summary'
      ],
      outputFormat: 'JSON with filesCreated (array), methods (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'methods', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        methods: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase4', 'implementation', 'lead-agent']
}));

export const updateMainEntryPointTask = defineTask('update-main-entry-point', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update main.py entry point',
  description: 'Update main.py to use new lead agent',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Update main.py to use the new SDK-based lead agent',
      context: {
        leadAgentResult: args.leadAgentResult,
        targetFile: 'main.py',
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read docs/REWRITE_PLAN.md for main.py specification',
        'Read existing main.py to understand current structure',
        'Rename existing main.py to main_legacy.py (preserve for rollback)',
        'Create new main.py that:',
        '  - Imports from agents.lead_agent import run_interactive',
        '  - Loads config and validates required variables',
        '  - Configures logging',
        '  - Runs asyncio.run(run_interactive())',
        '  - Has proper error handling',
        'Follow the code example in REWRITE_PLAN.md',
        'Return summary'
      ],
      outputFormat: 'JSON with filesCreated (array), filesRenamed (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        filesRenamed: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase4', 'entry-point']
}));

export const runLeadAgentIntegrationTestsTask = defineTask('run-lead-agent-integration-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Run lead agent integration tests',
  description: 'Run integration tests for lead agent',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer',
      task: 'Run integration tests and verify lead agent functionality',
      context: {
        targetQuality: args.targetQuality,
        testCommand: 'uv run python -m pytest tests/test_lead_agent_integration.py -v'
      },
      instructions: [
        'Run integration tests for lead agent',
        'Verify:',
        '  - Subagents invoked in correct order',
        '  - File-based coordination works',
        '  - Session directory created correctly',
        '  - tool_calls.jsonl shows parent-child relationships',
        '  - transcript.txt is human-readable',
        'Report pass/fail status',
        'Return detailed results'
      ],
      outputFormat: 'JSON with passed (boolean), testCount (number), failures (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['passed', 'testCount'],
      properties: {
        passed: { type: 'boolean' },
        testCount: { type: 'number' },
        failures: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase4', 'integration', 'testing']
}));

export const runPhase4QualityCheckTask = defineTask('run-phase4-quality-check', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Phase 4 quality check',
  description: 'Run tests and check coverage for lead agent',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer',
      task: 'Run tests and verify Phase 4 quality gate criteria',
      context: {
        targetQuality: args.targetQuality,
        targetCoverage: args.targetCoverage,
        testCommand: 'uv run python -m pytest tests/test_lead_agent.py tests/test_lead_agent_integration.py -v',
        coverageCommand: 'uv run python -m pytest tests/test_lead_agent.py tests/test_lead_agent_integration.py --cov=agents/lead_agent --cov-report=term-missing'
      },
      instructions: [
        'Run the test suite for lead agent',
        'Run coverage analysis',
        'Verify gate criteria:',
        '  - 95% coverage on lead_agent.py',
        '  - Integration tests pass',
        'Calculate quality score',
        'Return detailed metrics'
      ],
      outputFormat: 'JSON with qualityScore (number), testCount (number), coverage (number), gatePassed (boolean)'
    },
    outputSchema: {
      type: 'object',
      required: ['qualityScore', 'testCount', 'coverage'],
      properties: {
        qualityScore: { type: 'number' },
        testCount: { type: 'number' },
        coverage: { type: 'number' },
        gatePassed: { type: 'boolean' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase4', 'quality']
}));

// ============================================================================
// TASK DEFINITIONS - PHASE 5
// ============================================================================

export const runAllTestsTask = defineTask('run-all-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: `Run all tests (iteration ${args.iteration})`,
  description: 'Execute complete test suite',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer',
      task: 'Run the complete test suite and report results',
      context: {
        iteration: args.iteration,
        testCommand: 'uv run python -m pytest tests/ -v'
      },
      instructions: [
        'Run all tests in tests/ directory',
        'Collect pass/fail counts',
        'Identify any failures',
        'Report total test count',
        'Return detailed results'
      ],
      outputFormat: 'JSON with passed (boolean), total (number), failures (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['passed', 'total'],
      properties: {
        passed: { type: 'boolean' },
        total: { type: 'number' },
        failures: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase5', 'testing']
}));

export const checkCoverageTask = defineTask('check-coverage', (args, taskCtx) => ({
  kind: 'agent',
  title: `Check coverage (iteration ${args.iteration})`,
  description: 'Analyze code coverage for critical paths',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer',
      task: 'Analyze coverage for overall and critical paths',
      context: {
        iteration: args.iteration,
        criticalPaths: args.criticalPaths,
        targetCriticalCoverage: args.targetCriticalCoverage,
        targetOverallCoverage: args.targetOverallCoverage,
        coverageCommand: 'uv run python -m pytest tests/ --cov=. --cov-report=term-missing'
      },
      instructions: [
        'Run coverage analysis',
        'Calculate overall coverage percentage',
        'Calculate coverage for critical paths:',
        '  - mcp_servers/datadog_server.py',
        '  - mcp_servers/github_server.py',
        '  - utils/session_manager.py',
        '  - utils/hooks.py',
        '  - agents/lead_agent.py',
        'Identify coverage gaps',
        'Return detailed metrics'
      ],
      outputFormat: 'JSON with overallCoverage (number), criticalPathCoverage (number), gaps (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['overallCoverage', 'criticalPathCoverage'],
      properties: {
        overallCoverage: { type: 'number' },
        criticalPathCoverage: { type: 'number' },
        gaps: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase5', 'coverage']
}));

export const refineTestsAndCoverageTask = defineTask('refine-tests-coverage', (args, taskCtx) => ({
  kind: 'agent',
  title: `Refine tests and coverage (iteration ${args.iteration})`,
  description: 'Add tests to improve coverage and fix failures',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python test engineer',
      task: 'Add tests to close coverage gaps and fix failing tests',
      context: {
        iteration: args.iteration,
        coverageGaps: args.coverageGaps,
        failingTests: args.failingTests
      },
      instructions: [
        'Analyze coverage gaps',
        'Add tests for uncovered code paths',
        'Fix any failing tests',
        'Focus on critical paths first',
        'Return summary of changes'
      ],
      outputFormat: 'JSON with testsAdded (array), testsFixes (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['testsAdded', 'summary'],
      properties: {
        testsAdded: { type: 'array', items: { type: 'string' } },
        testsFixes: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase5', 'refinement']
}));

export const comparisonTestTask = defineTask('comparison-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Comparison test with legacy',
  description: 'Compare new system output with legacy system',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer',
      task: 'Compare new SDK-based system with legacy system output',
      context: {
        testCases: args.testCases
      },
      instructions: [
        'Prepare test cases with known inputs',
        'Run both legacy (main_legacy.py) and new (main.py) systems',
        'Compare output quality:',
        '  - Report structure',
        '  - Root cause identification',
        '  - Completeness',
        'Determine if new system produces equivalent or better results',
        'Return comparison results'
      ],
      outputFormat: 'JSON with equivalent (boolean), newSystemBetter (boolean), comparison (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['equivalent'],
      properties: {
        equivalent: { type: 'boolean' },
        newSystemBetter: { type: 'boolean' },
        comparison: { type: 'array', items: { type: 'object' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase5', 'comparison']
}));

// ============================================================================
// TASK DEFINITIONS - PHASE 6
// ============================================================================

export const securityReviewTask = defineTask('security-review', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Security review',
  description: 'Review code for security issues',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'security engineer',
      task: 'Review code for security issues',
      context: {
        files: [
          'agents/lead_agent.py',
          'mcp_servers/datadog_server.py',
          'mcp_servers/github_server.py',
          'utils/hooks.py',
          'utils/session_manager.py'
        ]
      },
      instructions: [
        'Review all new code files',
        'Check for:',
        '  - API credentials not logged',
        '  - No secrets in logs or transcripts',
        '  - Permission mode properly configurable',
        '  - Rate limiting in place',
        '  - Safe input handling',
        'Verify no sensitive data exposure',
        'Return security assessment'
      ],
      outputFormat: 'JSON with passed (boolean), issues (array), recommendations (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['passed'],
      properties: {
        passed: { type: 'boolean' },
        issues: { type: 'array', items: { type: 'string' } },
        recommendations: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase6', 'security']
}));

export const updateDocumentationTask = defineTask('update-documentation', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update documentation',
  description: 'Update CLAUDE.md and README with new architecture',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'technical writer',
      task: 'Update documentation to reflect new SDK-based architecture',
      context: {
        files: ['CLAUDE.md', 'README.md'],
        rewritePlan: 'docs/REWRITE_PLAN.md'
      },
      instructions: [
        'Read current CLAUDE.md and README.md',
        'Update CLAUDE.md with:',
        '  - New architecture overview (SDK-based)',
        '  - Updated file structure (mcp_servers/, new agents/)',
        '  - New commands and usage',
        '  - Subagent descriptions',
        '  - Session management details',
        'Update README.md with:',
        '  - Installation updates',
        '  - New running instructions',
        '  - Architecture diagram if needed',
        'Return updated status'
      ],
      outputFormat: 'JSON with updated (boolean), filesModified (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['updated'],
      properties: {
        updated: { type: 'boolean' },
        filesModified: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase6', 'documentation']
}));

export const moveLegacyCodeTask = defineTask('move-legacy-code', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Move legacy code',
  description: 'Move legacy code to legacy/ directory',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'developer',
      task: 'Archive legacy code to legacy/ directory',
      context: {
        legacyFiles: [
          'agents/main_agent.py',
          'agents/datadog_retriever.py',
          'agents/deployment_checker.py',
          'agents/code_checker.py',
          'agents/exception_analyzer.py',
          'main_legacy.py'
        ]
      },
      instructions: [
        'Create legacy/ directory',
        'Create legacy/agents/ subdirectory',
        'Move legacy agent files to legacy/agents/',
        'Move main_legacy.py to legacy/',
        'Create legacy/README.md with deprecation notice',
        'Return status'
      ],
      outputFormat: 'JSON with moved (boolean), filesMoved (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['moved'],
      properties: {
        moved: { type: 'boolean' },
        filesMoved: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase6', 'migration']
}));

export const productionSmokeTestTask = defineTask('production-smoke-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Production smoke tests',
  description: 'Run smoke tests with real API calls',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer',
      task: 'Run smoke tests to verify production readiness',
      context: {
        testCount: args.testCount
      },
      instructions: [
        'Run smoke tests with actual API calls (if credentials available)',
        'Test scenarios:',
        '  - Mode 1: Log message search',
        '  - Mode 2: Identifier search',
        '  - Error handling',
        'Verify complete workflow:',
        '  - DataDog search works',
        '  - GitHub search works',
        '  - Report generated',
        '  - Session logs created',
        'Return test results'
      ],
      outputFormat: 'JSON with allPassed (boolean), successRate (number), results (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['allPassed', 'successRate'],
      properties: {
        allPassed: { type: 'boolean' },
        successRate: { type: 'number' },
        results: { type: 'array', items: { type: 'object' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['phase6', 'smoke-test']
}));
