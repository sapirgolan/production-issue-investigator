/**
 * @process production-issue-investigator
 * @description Phased implementation of AI agent for production issue investigation using Claude Agent SDK
 * @inputs { designDocPath: string }
 * @outputs { success: boolean, phases: array, artifacts: object }
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * Production Issue Investigator Implementation Process
 *
 * 5-Phase Implementation with Quality Gates:
 * Phase 1: Foundation - Project setup, .env, logging, time utils, DataDog API wrapper
 * Phase 2: DataDog Sub-Agent - Log retrieval with Mode 1/2, session-based search
 * Phase 3: Deployment Checker - GitHub integration, kubernetes commit correlation
 * Phase 4: Code Checker - Version comparison, diff generation, code analysis
 * Phase 5: Reporting + Integration - Full orchestration, report generation
 */
export async function process(inputs, ctx) {
  const { designDocPath = 'docs/designs/production-issue-investigator-design.md' } = inputs;

  const phaseResults = [];

  // ============================================================================
  // PHASE 1: FOUNDATION
  // ============================================================================

  await ctx.breakpoint({
    question: 'Starting Phase 1: Foundation. This phase will implement project infrastructure including .env loading, logging, time utilities, and DataDog API wrapper with rate limit handling. Ready to proceed?',
    title: 'Phase 1: Foundation',
    context: { runId: ctx.runId }
  });

  const phase1Result = await ctx.task(implementPhase1Task, {
    designDocPath,
    phase: 1,
    components: [
      'utils/config.py - Environment loading and validation',
      'utils/logger.py - Logging infrastructure with rotation',
      'utils/time_utils.py - Complete datetime parsing and timezone conversion',
      'utils/datadog_api.py - DataDog API wrapper with rate limit handling'
    ]
  });

  // Phase 1 Verification
  const phase1Verification = await ctx.task(verifyPhase1Task, {
    phase: 1,
    expectedFiles: [
      'utils/config.py',
      'utils/logger.py',
      'utils/time_utils.py',
      'utils/datadog_api.py'
    ],
    testCriteria: [
      'Environment variables loaded from .env',
      'Logging configured with rotation',
      'Time parsing works with various formats',
      'Tel Aviv to UTC conversion works correctly',
      'DataDog API client initializes and handles rate limits'
    ]
  });

  phaseResults.push({
    phase: 1,
    name: 'Foundation',
    implementation: phase1Result,
    verification: phase1Verification,
    success: phase1Verification.allPassed
  });

  if (!phase1Verification.allPassed) {
    await ctx.breakpoint({
      question: `Phase 1 verification failed. ${phase1Verification.failedTests?.length || 0} tests failed. Review and fix issues before proceeding?`,
      title: 'Phase 1 Verification Failed',
      context: { runId: ctx.runId }
    });
  }

  // ============================================================================
  // PHASE 2: DATADOG SUB-AGENT + BASIC ORCHESTRATION
  // ============================================================================

  await ctx.breakpoint({
    question: 'Starting Phase 2: DataDog Sub-Agent. This phase implements log retrieval with Mode 1 (log message) and Mode 2 (identifiers) search, session-based retrieval, and time window expansion. Ready to proceed?',
    title: 'Phase 2: DataDog Sub-Agent',
    context: { runId: ctx.runId }
  });

  const phase2Result = await ctx.task(implementPhase2Task, {
    designDocPath,
    phase: 2,
    components: [
      'agents/datadog_retriever.py - Complete DataDog sub-agent with Mode 1/2 search',
      'agents/main_agent.py - Basic orchestration with input mode detection',
      'main.py - Interactive chat entry point'
    ],
    dependencies: phase1Result
  });

  const phase2Verification = await ctx.task(verifyPhase2Task, {
    phase: 2,
    testCriteria: [
      'Mode 1 search by log message works',
      'Mode 2 search by identifiers works',
      'Session-based retrieval (efilogid) works',
      'Time window calculation correct',
      'Time window expansion on no results',
      'Service extraction from logs works',
      'Main agent asks user for input mode'
    ]
  });

  phaseResults.push({
    phase: 2,
    name: 'DataDog Sub-Agent',
    implementation: phase2Result,
    verification: phase2Verification,
    success: phase2Verification.allPassed
  });

  if (!phase2Verification.allPassed) {
    await ctx.breakpoint({
      question: `Phase 2 verification failed. Review issues and fix before proceeding to Phase 3?`,
      title: 'Phase 2 Verification Failed',
      context: { runId: ctx.runId }
    });
  }

  // ============================================================================
  // PHASE 3: DEPLOYMENT CHECKER SUB-AGENT
  // ============================================================================

  await ctx.breakpoint({
    question: 'Starting Phase 3: Deployment Checker. This phase implements GitHub integration, kubernetes commit search, PR retrieval, and deployment correlation. Ready to proceed?',
    title: 'Phase 3: Deployment Checker',
    context: { runId: ctx.runId }
  });

  const phase3Result = await ctx.task(implementPhase3Task, {
    designDocPath,
    phase: 3,
    components: [
      'utils/github_helper.py - GitHub MCP + CLI wrapper with fallback',
      'agents/deployment_checker.py - Deployment checker sub-agent',
      'agents/main_agent.py - Updated with parallel service investigation'
    ],
    dependencies: [phase1Result, phase2Result]
  });

  const phase3Verification = await ctx.task(verifyPhase3Task, {
    phase: 3,
    testCriteria: [
      'GitHub API/CLI connection works',
      'Kubernetes repo commit search works',
      'Commit title pattern parsing works',
      '72-hour window filtering works',
      'PR retrieval for commits works',
      'Changed files extraction from PR works',
      'Repository mapping fallback for -jobs services'
    ]
  });

  phaseResults.push({
    phase: 3,
    name: 'Deployment Checker',
    implementation: phase3Result,
    verification: phase3Verification,
    success: phase3Verification.allPassed
  });

  if (!phase3Verification.allPassed) {
    await ctx.breakpoint({
      question: `Phase 3 verification failed. Review issues and fix before proceeding to Phase 4?`,
      title: 'Phase 3 Verification Failed',
      context: { runId: ctx.runId }
    });
  }

  // ============================================================================
  // PHASE 4: CODE CHECKER SUB-AGENT
  // ============================================================================

  await ctx.breakpoint({
    question: 'Starting Phase 4: Code Checker. This phase implements file path mapping, version comparison, diff generation, and code analysis. Ready to proceed?',
    title: 'Phase 4: Code Checker',
    context: { runId: ctx.runId }
  });

  const phase4Result = await ctx.task(implementPhase4Task, {
    designDocPath,
    phase: 4,
    components: [
      'agents/code_checker.py - Code checker sub-agent with version comparison',
      'agents/main_agent.py - Updated with Code Checker integration'
    ],
    dependencies: [phase1Result, phase2Result, phase3Result]
  });

  const phase4Verification = await ctx.task(verifyPhase4Task, {
    phase: 4,
    testCriteria: [
      'Logger name to file path mapping works (.kt and .java)',
      'dd.version parsing extracts commit hash correctly',
      'File fetch at specific commit works',
      'Diff generation between versions works',
      'Code analysis identifies potential issues',
      'Sequential execution after deployment checker'
    ]
  });

  phaseResults.push({
    phase: 4,
    name: 'Code Checker',
    implementation: phase4Result,
    verification: phase4Verification,
    success: phase4Verification.allPassed
  });

  if (!phase4Verification.allPassed) {
    await ctx.breakpoint({
      question: `Phase 4 verification failed. Review issues and fix before proceeding to Phase 5?`,
      title: 'Phase 4 Verification Failed',
      context: { runId: ctx.runId }
    });
  }

  // ============================================================================
  // PHASE 5: REPORTING + FULL INTEGRATION
  // ============================================================================

  await ctx.breakpoint({
    question: 'Starting Phase 5: Reporting + Full Integration. This phase implements the report generator, full orchestration, error handling, and comprehensive testing. Ready to proceed?',
    title: 'Phase 5: Reporting + Integration',
    context: { runId: ctx.runId }
  });

  const phase5Result = await ctx.task(implementPhase5Task, {
    designDocPath,
    phase: 5,
    components: [
      'utils/report_generator.py - Markdown report generation',
      'agents/main_agent.py - Full orchestration with all sub-agents',
      'main.py - Complete interactive chat interface'
    ],
    dependencies: [phase1Result, phase2Result, phase3Result, phase4Result]
  });

  const phase5Verification = await ctx.task(verifyPhase5Task, {
    phase: 5,
    testCriteria: [
      'Report generator produces valid Markdown',
      'All report sections populated correctly',
      'Full orchestration flow works end-to-end',
      'Parallel service investigation works',
      'Error handling and partial results work',
      'Investigation methodologies applied when needed (Mode 2)',
      'User follow-up questions work when stuck'
    ]
  });

  phaseResults.push({
    phase: 5,
    name: 'Reporting + Integration',
    implementation: phase5Result,
    verification: phase5Verification,
    success: phase5Verification.allPassed
  });

  // ============================================================================
  // FINAL INTEGRATION TEST
  // ============================================================================

  await ctx.breakpoint({
    question: 'All phases completed. Running final integration test with real production scenario. This will test the complete flow with actual DataDog and GitHub APIs. Proceed?',
    title: 'Final Integration Test',
    context: { runId: ctx.runId }
  });

  const integrationTestResult = await ctx.task(runIntegrationTestTask, {
    scenarios: [
      'Mode 1: Search by log message with known error',
      'Mode 2: Search by customer identifier',
      'Multiple services correlation',
      'Time window edge cases',
      'Error handling with partial results'
    ]
  });

  // Final summary
  await ctx.breakpoint({
    question: `Implementation complete! ${phaseResults.filter(p => p.success).length}/5 phases passed verification. Integration tests: ${integrationTestResult.passed}/${integrationTestResult.total}. Review final deliverable and approve?`,
    title: 'Implementation Complete',
    context: {
      runId: ctx.runId,
      files: [
        { path: 'artifacts/implementation-summary.md', format: 'markdown' }
      ]
    }
  });

  return {
    success: phaseResults.every(p => p.success) && integrationTestResult.allPassed,
    phases: phaseResults,
    integrationTest: integrationTestResult,
    artifacts: {
      agents: ['agents/main_agent.py', 'agents/datadog_retriever.py', 'agents/deployment_checker.py', 'agents/code_checker.py'],
      utils: ['utils/config.py', 'utils/logger.py', 'utils/time_utils.py', 'utils/datadog_api.py', 'utils/github_helper.py', 'utils/report_generator.py'],
      entryPoint: 'main.py'
    },
    metadata: {
      processId: 'production-issue-investigator',
      timestamp: ctx.now()
    }
  };
}

// ============================================================================
// PHASE 1 TASKS
// ============================================================================

export const implementPhase1Task = defineTask('implement-phase-1', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Phase 1: Implement Foundation',
  description: 'Implement project infrastructure: config, logging, time utils, DataDog API wrapper',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer implementing production infrastructure',
      task: 'Implement Phase 1 Foundation components following the design document specifications',
      context: {
        designDocPath: args.designDocPath,
        components: args.components,
        phase: args.phase
      },
      instructions: [
        'Read the design document for detailed specifications',
        'Implement utils/config.py for environment loading with validation',
        'Implement utils/logger.py with file rotation (10MB, 5 backups)',
        'Complete utils/time_utils.py with all datetime functions including time window calculation',
        'Implement utils/datadog_api.py with full API wrapper including rate limit handling',
        'Use python-dotenv for .env loading',
        'Use pytz for timezone handling (Tel Aviv -> UTC)',
        'Handle X-RateLimit-* headers from DataDog API',
        'Add proper type hints and docstrings',
        'Write code tests for each component'
      ],
      outputFormat: 'JSON with files created, code summaries, and test results'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' },
        testsWritten: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['implementation', 'phase-1', 'foundation']
}));

export const verifyPhase1Task = defineTask('verify-phase-1', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify Phase 1: Foundation',
  description: 'Verify Phase 1 implementation meets requirements',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer verifying implementation',
      task: 'Verify Phase 1 Foundation implementation is complete and functional',
      context: {
        expectedFiles: args.expectedFiles,
        testCriteria: args.testCriteria
      },
      instructions: [
        'Check all expected files exist and are properly implemented',
        'Run tests for each component',
        'Verify environment loading works with .env file',
        'Test logging configuration and rotation',
        'Test time parsing with various input formats',
        'Test Tel Aviv to UTC conversion',
        'Test DataDog API wrapper initialization',
        'Verify rate limit handling logic',
        'Report any issues found'
      ],
      outputFormat: 'JSON with test results, pass/fail status, and issues found'
    },
    outputSchema: {
      type: 'object',
      required: ['allPassed', 'testResults'],
      properties: {
        allPassed: { type: 'boolean' },
        testResults: { type: 'array', items: { type: 'object' } },
        failedTests: { type: 'array', items: { type: 'object' } },
        issues: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['verification', 'phase-1', 'testing']
}));

// ============================================================================
// PHASE 2 TASKS
// ============================================================================

export const implementPhase2Task = defineTask('implement-phase-2', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Phase 2: Implement DataDog Sub-Agent',
  description: 'Implement DataDog retriever with Mode 1/2 search and session retrieval',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer implementing Claude Agent SDK sub-agent',
      task: 'Implement Phase 2 DataDog Sub-Agent with full log retrieval capabilities',
      context: {
        designDocPath: args.designDocPath,
        components: args.components,
        dependencies: args.dependencies
      },
      instructions: [
        'Read the design document for DataDog search specifications',
        'Implement agents/datadog_retriever.py as Claude Agent SDK sub-agent',
        'Implement Mode 1 search: log message + optional datetime',
        'Implement Mode 2 search: identifiers (CID, card_account_id, paymentId) + optional datetime',
        'Implement session-based retrieval using efilogid (Step 2)',
        'Implement time window calculation (default 4h, with datetime ±2h)',
        'Implement time window expansion retry logic (24h, then 7 days)',
        'Never expand time window into the future',
        'Extract services, efilogids, dd.version from responses',
        'Limit efilogid retrieval to 20-30 unique sessions',
        'Prioritize ERROR-level logs, recent timestamps',
        'Implement comprehensive logging of all actions',
        'Update main_agent.py with basic orchestration and input mode detection',
        'Agent must explicitly ask user to select Mode 1 or Mode 2'
      ],
      outputFormat: 'JSON with implementation details'
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

  labels: ['implementation', 'phase-2', 'datadog']
}));

export const verifyPhase2Task = defineTask('verify-phase-2', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify Phase 2: DataDog Sub-Agent',
  description: 'Verify DataDog sub-agent implementation',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer verifying DataDog integration',
      task: 'Verify Phase 2 DataDog Sub-Agent is complete and functional',
      context: {
        testCriteria: args.testCriteria
      },
      instructions: [
        'Test Mode 1 search with sample log message',
        'Test Mode 2 search with sample identifiers',
        'Verify session-based retrieval logic',
        'Test time window calculation for various scenarios',
        'Test time window expansion on no results',
        'Verify service extraction from log responses',
        'Test main agent input mode prompt',
        'Run integration test against real DataDog API if possible'
      ],
      outputFormat: 'JSON with test results'
    },
    outputSchema: {
      type: 'object',
      required: ['allPassed', 'testResults'],
      properties: {
        allPassed: { type: 'boolean' },
        testResults: { type: 'array', items: { type: 'object' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['verification', 'phase-2', 'testing']
}));

// ============================================================================
// PHASE 3 TASKS
// ============================================================================

export const implementPhase3Task = defineTask('implement-phase-3', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Phase 3: Implement Deployment Checker',
  description: 'Implement GitHub helper and deployment checker sub-agent',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer implementing GitHub integration',
      task: 'Implement Phase 3 Deployment Checker with GitHub MCP/CLI integration',
      context: {
        designDocPath: args.designDocPath,
        components: args.components,
        dependencies: args.dependencies
      },
      instructions: [
        'Read the design document for deployment checker specifications',
        'Implement utils/github_helper.py with MCP primary + CLI fallback',
        'Implement agents/deployment_checker.py as Claude Agent SDK sub-agent',
        'Search sunbit-dev/kubernetes repo for service commits',
        'Use 72-hour window BEFORE the DataDog search timestamp',
        'Parse commit title pattern: {service-name}-{commit_hash}___{build_number}',
        'Correlate dd.version with kubernetes commit titles',
        'Extract application commit hash (part before ___)',
        'Find associated closed PR for each commit',
        'Retrieve list of changed files from PR',
        'Implement repository mapping: {service-name} -> sunbit-dev/{service-name}',
        'Implement fallback: remove -jobs from name if repo not found',
        'Handle 404 errors gracefully, skip Code Checker if repo not found',
        'Update main_agent.py for parallel service investigation'
      ],
      outputFormat: 'JSON with implementation details'
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

  labels: ['implementation', 'phase-3', 'deployment']
}));

export const verifyPhase3Task = defineTask('verify-phase-3', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify Phase 3: Deployment Checker',
  description: 'Verify deployment checker implementation',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer verifying GitHub integration',
      task: 'Verify Phase 3 Deployment Checker is complete and functional',
      context: {
        testCriteria: args.testCriteria
      },
      instructions: [
        'Test GitHub API/CLI connection',
        'Test kubernetes repo commit search',
        'Verify commit title pattern parsing',
        'Test 72-hour window filtering',
        'Test PR retrieval for commits',
        'Verify changed files extraction',
        'Test repository mapping with -jobs fallback'
      ],
      outputFormat: 'JSON with test results'
    },
    outputSchema: {
      type: 'object',
      required: ['allPassed', 'testResults'],
      properties: {
        allPassed: { type: 'boolean' },
        testResults: { type: 'array', items: { type: 'object' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['verification', 'phase-3', 'testing']
}));

// ============================================================================
// PHASE 4 TASKS
// ============================================================================

export const implementPhase4Task = defineTask('implement-phase-4', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Phase 4: Implement Code Checker',
  description: 'Implement code checker sub-agent with version comparison',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer implementing code analysis',
      task: 'Implement Phase 4 Code Checker with version comparison and diff generation',
      context: {
        designDocPath: args.designDocPath,
        components: args.components,
        dependencies: args.dependencies
      },
      instructions: [
        'Read the design document for code checker specifications',
        'Implement agents/code_checker.py as Claude Agent SDK sub-agent',
        'Map logger_name to file path: com.sunbit.x.y.z.ClassName -> src/main/kotlin/com/sunbit/x/y/z/ClassName.kt',
        'Fallback to .java extension if .kt not found',
        'Extract dd.version from DataDog logs (format: {commit_hash}___{build_number})',
        'Use deployed version (dd.version commit hash) and parent commit for comparison',
        'Fetch file content at specific commits using GitHub API',
        'Generate full diff between versions',
        'Analyze code changes for potential issues:',
        '  - Removed error handling',
        '  - Changed business logic',
        '  - New exceptions introduced',
        '  - Modified SQL/database queries',
        '  - Changed external API calls',
        '  - Modified timing/async behavior',
        '  - Security concerns',
        'Run Code Checker sequentially after Deployment Checker (needs commit hash)',
        'Update main_agent.py with Code Checker integration'
      ],
      outputFormat: 'JSON with implementation details'
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

  labels: ['implementation', 'phase-4', 'code-checker']
}));

export const verifyPhase4Task = defineTask('verify-phase-4', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify Phase 4: Code Checker',
  description: 'Verify code checker implementation',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer verifying code analysis',
      task: 'Verify Phase 4 Code Checker is complete and functional',
      context: {
        testCriteria: args.testCriteria
      },
      instructions: [
        'Test logger name to file path mapping for .kt files',
        'Test fallback to .java extension',
        'Verify dd.version parsing extracts commit hash',
        'Test file fetch at specific commit',
        'Verify diff generation between versions',
        'Test code analysis output for sample changes',
        'Verify sequential execution after deployment checker'
      ],
      outputFormat: 'JSON with test results'
    },
    outputSchema: {
      type: 'object',
      required: ['allPassed', 'testResults'],
      properties: {
        allPassed: { type: 'boolean' },
        testResults: { type: 'array', items: { type: 'object' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['verification', 'phase-4', 'testing']
}));

// ============================================================================
// PHASE 5 TASKS
// ============================================================================

export const implementPhase5Task = defineTask('implement-phase-5', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Phase 5: Implement Reporting + Integration',
  description: 'Implement report generator and full orchestration',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer implementing full system integration',
      task: 'Implement Phase 5 Reporting and Full Integration',
      context: {
        designDocPath: args.designDocPath,
        components: args.components,
        dependencies: args.dependencies
      },
      instructions: [
        'Read the design document for report format specification',
        'Implement utils/report_generator.py with Markdown template',
        'Include all report sections from design doc:',
        '  - Executive Summary',
        '  - Timeline',
        '  - Services Involved',
        '  - Root Cause Analysis (with confidence level)',
        '  - Evidence (logs, diffs, deployments)',
        '  - Proposed Fix (with risk assessment)',
        '  - Testing Required',
        '  - Files to Modify',
        '  - Next Steps for Developer',
        '  - Investigation Details (sub-agent results)',
        '  - Investigation Methodologies (only if critical)',
        'Complete main_agent.py with full orchestration:',
        '  - Input mode detection and prompting',
        '  - DataDog search coordination',
        '  - Parallel service investigation',
        '  - Result aggregation',
        '  - Report generation',
        'Implement investigation methodologies for Mode 2 when results unclear',
        'Handle partial results gracefully',
        'Implement user follow-up questions when stuck',
        'Complete main.py as interactive chat entry point',
        'Display report to console with formatting'
      ],
      outputFormat: 'JSON with implementation details'
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

  labels: ['implementation', 'phase-5', 'reporting']
}));

export const verifyPhase5Task = defineTask('verify-phase-5', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify Phase 5: Reporting + Integration',
  description: 'Verify reporting and full integration',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer verifying full system',
      task: 'Verify Phase 5 Reporting and Integration is complete',
      context: {
        testCriteria: args.testCriteria
      },
      instructions: [
        'Verify report generator produces valid Markdown',
        'Check all report sections are populated',
        'Test full orchestration flow end-to-end',
        'Verify parallel service investigation',
        'Test error handling with partial results',
        'Verify investigation methodologies applied for Mode 2',
        'Test user follow-up questions'
      ],
      outputFormat: 'JSON with test results'
    },
    outputSchema: {
      type: 'object',
      required: ['allPassed', 'testResults'],
      properties: {
        allPassed: { type: 'boolean' },
        testResults: { type: 'array', items: { type: 'object' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['verification', 'phase-5', 'testing']
}));

// ============================================================================
// INTEGRATION TEST TASK
// ============================================================================

export const runIntegrationTestTask = defineTask('run-integration-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Final Integration Test',
  description: 'Run comprehensive integration tests with real APIs',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer running integration tests',
      task: 'Run comprehensive integration tests for the complete system',
      context: {
        scenarios: args.scenarios
      },
      instructions: [
        'Run complete flow tests with real DataDog and GitHub APIs',
        'Test Mode 1: Search by log message',
        'Test Mode 2: Search by identifiers',
        'Test multiple services correlation',
        'Test time window edge cases',
        'Test error handling with partial results',
        'Verify report generation for each scenario',
        'Document any issues found'
      ],
      outputFormat: 'JSON with test results'
    },
    outputSchema: {
      type: 'object',
      required: ['allPassed', 'total', 'passed'],
      properties: {
        allPassed: { type: 'boolean' },
        total: { type: 'number' },
        passed: { type: 'number' },
        results: { type: 'array', items: { type: 'object' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['integration-test', 'final-verification']
}));
