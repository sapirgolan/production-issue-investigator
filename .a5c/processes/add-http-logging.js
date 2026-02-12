/**
 * @process add-http-logging
 * @description Add comprehensive HTTP/MCP logging to all subagents with TDD approach
 * @inputs { targetQuality: number }
 * @outputs { success: boolean, finalQuality: number }
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * Add HTTP/MCP Logging Process
 *
 * Adds detailed logging for:
 * - DataDog API HTTP calls (body, headers, URL, response)
 * - GitHub MCP tool calls (tool name, parameters)
 *
 * Uses TDD approach with quality convergence loop.
 */
export async function process(inputs, ctx) {
  const { targetQuality = 85 } = inputs;

  // ============================================================================
  // PHASE 1: ANALYZE CURRENT CODEBASE
  // ============================================================================

  const analysisResult = await ctx.task(analyzeHttpCallsTask, {
    description: 'Identify all HTTP calls and MCP tool usages in the codebase'
  });

  // ============================================================================
  // PHASE 2: DESIGN LOGGING APPROACH
  // ============================================================================

  const designResult = await ctx.task(designLoggingApproachTask, {
    description: 'Design logging strategy and structure',
    analysisResult
  });

  // Breakpoint: Review design
  await ctx.breakpoint({
    question: 'Review the logging design. Does it meet requirements for HTTP body logging and MCP tool logging?',
    title: 'Design Review',
    context: { runId: ctx.runId }
  });

  // ============================================================================
  // PHASE 3: TDD IMPLEMENTATION LOOP
  // ============================================================================

  let iteration = 0;
  let currentQuality = 0;
  let converged = false;
  const maxIterations = 5;
  const implementationResults = [];

  while (iteration < maxIterations && !converged) {
    iteration++;

    // Step 1: Write tests for logging behavior
    const testResult = await ctx.task(writeLoggingTestsTask, {
      iteration,
      designResult,
      previousFeedback: iteration > 1 ? implementationResults[iteration - 2].feedback : null
    });

    // Step 2: Implement logging functionality
    const implementResult = await ctx.task(implementLoggingTask, {
      iteration,
      designResult,
      testResult,
      previousFeedback: iteration > 1 ? implementationResults[iteration - 2].feedback : null
    });

    // Step 3: Run tests and measure quality
    const qualityResult = await ctx.task(runTestsAndQualityCheckTask, {
      iteration,
      targetQuality,
      testResult,
      implementResult
    });

    currentQuality = qualityResult.qualityScore;

    implementationResults.push({
      iteration,
      quality: currentQuality,
      tests: testResult,
      implementation: implementResult,
      qualityCheck: qualityResult,
      feedback: qualityResult.feedback
    });

    if (currentQuality >= targetQuality) {
      converged = true;
    } else if (iteration < maxIterations) {
      // Continue to next iteration with feedback
      await ctx.task(refineImplementationTask, {
        iteration,
        feedback: qualityResult.feedback,
        targetQuality
      });
    }
  }

  // ============================================================================
  // PHASE 4: INTEGRATION TESTING
  // ============================================================================

  const integrationResult = await ctx.task(integrationTestTask, {
    description: 'Test logging in real scenarios with actual HTTP calls',
    targetQuality,
    currentQuality
  });

  // ============================================================================
  // PHASE 5: FINAL VERIFICATION
  // ============================================================================

  const finalVerification = await ctx.task(finalVerificationTask, {
    targetQuality,
    currentQuality,
    converged,
    integrationResult
  });

  // Final breakpoint for approval
  if (converged) {
    await ctx.breakpoint({
      question: `Quality score ${currentQuality}% meets target ${targetQuality}%. Approve HTTP logging changes?`,
      title: 'Final Approval',
      context: { runId: ctx.runId }
    });
  }

  return {
    success: converged,
    iterations: iteration,
    finalQuality: currentQuality,
    targetQuality,
    implementationResults,
    integrationResult,
    verification: finalVerification
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const analyzeHttpCallsTask = defineTask('analyze-http-calls', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Analyze HTTP calls in codebase',
  description: 'Identify all HTTP calls and MCP tool usages',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Analyze the codebase to identify all HTTP calls and MCP tool usages that need logging',
      context: {
        files: [
          'utils/datadog_api.py',
          'agents/datadog_retriever.py',
          'agents/deployment_checker.py',
          'agents/code_checker.py'
        ]
      },
      instructions: [
        'Read all the specified files',
        'Identify all places where HTTP calls are made (requests.request, self._make_request, etc.)',
        'Identify all places where MCP tools are called (GitHub tools)',
        'For each location, note: file path, line number, what data should be logged',
        'Return a structured summary of all HTTP/MCP call locations'
      ],
      outputFormat: 'JSON with httpCalls (array), mcpCalls (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['httpCalls', 'mcpCalls', 'summary'],
      properties: {
        httpCalls: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              file: { type: 'string' },
              line: { type: 'number' },
              method: { type: 'string' },
              whatToLog: { type: 'string' }
            }
          }
        },
        mcpCalls: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              file: { type: 'string' },
              agent: { type: 'string' },
              description: { type: 'string' }
            }
          }
        },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['analysis']
}));

export const designLoggingApproachTask = defineTask('design-logging-approach', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Design logging approach',
  description: 'Create logging strategy and structure',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior software architect',
      task: 'Design a comprehensive logging approach for HTTP and MCP calls',
      context: {
        analysisResult: args.analysisResult,
        requirements: [
          'Log full HTTP request body, headers, URL, method',
          'Log HTTP response status, headers, body (truncated if large)',
          'Log MCP tool name and parameters',
          'Use structured logging (JSON-like format)',
          'Add log level configuration (DEBUG for detailed, INFO for summary)',
          'Ensure no sensitive data is logged (API keys, tokens)'
        ]
      },
      instructions: [
        'Design logging utility functions or decorators',
        'Define what should be logged at each level (DEBUG vs INFO)',
        'Specify log format and structure',
        'Identify files that need to be modified',
        'Create implementation plan with specific steps',
        'Consider backward compatibility and existing logger usage'
      ],
      outputFormat: 'JSON with approach (string), logFormat (object), filesToModify (array), implementationPlan (array of steps)'
    },
    outputSchema: {
      type: 'object',
      required: ['approach', 'filesToModify', 'implementationPlan'],
      properties: {
        approach: { type: 'string' },
        logFormat: { type: 'object' },
        filesToModify: { type: 'array', items: { type: 'string' } },
        implementationPlan: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['design']
}));

export const writeLoggingTestsTask = defineTask('write-logging-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: `Write logging tests (iteration ${args.iteration})`,
  description: 'Create tests to verify logging behavior',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python test engineer',
      task: 'Write comprehensive tests for HTTP and MCP logging',
      context: {
        iteration: args.iteration,
        designResult: args.designResult,
        previousFeedback: args.previousFeedback
      },
      instructions: [
        'Create test file(s) for logging functionality',
        'Write tests that verify HTTP request logging (body, headers, URL)',
        'Write tests that verify HTTP response logging',
        'Write tests that verify MCP tool call logging',
        'Use mocks/patches to intercept logging calls',
        'Write tests for edge cases (large bodies, sensitive data redaction)',
        'Follow pytest and unittest patterns from existing tests',
        'Return summary of tests created'
      ],
      outputFormat: 'JSON with testsCreated (array of file paths), testCount (number), summary (string)'
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

  labels: ['testing', 'tdd', `iteration-${args.iteration}`]
}));

export const implementLoggingTask = defineTask('implement-logging', (args, taskCtx) => ({
  kind: 'agent',
  title: `Implement logging (iteration ${args.iteration})`,
  description: 'Add HTTP and MCP logging to the codebase',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Implement comprehensive HTTP and MCP logging',
      context: {
        iteration: args.iteration,
        designResult: args.designResult,
        testResult: args.testResult,
        previousFeedback: args.previousFeedback
      },
      instructions: [
        'Implement logging in utils/datadog_api.py for HTTP calls',
        'Add request logging before self._make_request calls (log body, headers, URL, method)',
        'Add response logging after HTTP calls (log status, headers, body excerpt)',
        'For MCP calls in agents: add logging when GitHub tools are invoked',
        'Use logger.debug for detailed logs (full bodies)',
        'Use logger.info for summary logs',
        'Ensure API keys and tokens are NOT logged',
        'Make tests pass',
        'Return summary of changes'
      ],
      outputFormat: 'JSON with filesModified (array), changes (array of descriptions), summary (string)'
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

  labels: ['implementation', `iteration-${args.iteration}`]
}));

export const runTestsAndQualityCheckTask = defineTask('run-tests-quality', (args, taskCtx) => ({
  kind: 'agent',
  title: `Run tests and check quality (iteration ${args.iteration})`,
  description: 'Execute tests and measure quality',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior QA engineer',
      task: 'Run tests and calculate quality score',
      context: {
        iteration: args.iteration,
        targetQuality: args.targetQuality,
        testCommand: 'uv run python -m pytest tests/ -v --tb=short',
        coverageCommand: 'uv run python -m pytest tests/ --cov=utils --cov=agents --cov-report=term-missing'
      },
      instructions: [
        'Run the full test suite',
        'Run coverage analysis',
        'Check that new logging tests pass',
        'Check that existing tests still pass',
        'Calculate quality score: (pass_rate * 0.6) + (coverage_rate * 0.4)',
        'Provide feedback if quality is below target',
        'Identify specific failures or coverage gaps'
      ],
      outputFormat: 'JSON with qualityScore (number 0-100), testsPassed (boolean), testsTotal (number), testsFailed (number), coveragePercent (number), feedback (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['qualityScore', 'testsPassed'],
      properties: {
        qualityScore: { type: 'number', minimum: 0, maximum: 100 },
        testsPassed: { type: 'boolean' },
        testsTotal: { type: 'number' },
        testsFailed: { type: 'number' },
        coveragePercent: { type: 'number' },
        feedback: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['testing', 'quality', `iteration-${args.iteration}`]
}));

export const refineImplementationTask = defineTask('refine-implementation', (args, taskCtx) => ({
  kind: 'agent',
  title: `Refine implementation (iteration ${args.iteration})`,
  description: 'Fix issues from previous iteration',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Fix issues identified in the quality check',
      context: {
        iteration: args.iteration,
        feedback: args.feedback,
        targetQuality: args.targetQuality
      },
      instructions: [
        'Analyze feedback from previous iteration',
        'Fix any failing tests',
        'Improve coverage if needed',
        'Refine logging implementation',
        'Ensure backward compatibility',
        'Return summary of refinements'
      ],
      outputFormat: 'JSON with refined (boolean), changes (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['refined', 'summary'],
      properties: {
        refined: { type: 'boolean' },
        changes: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['refinement', `iteration-${args.iteration}`]
}));

export const integrationTestTask = defineTask('integration-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Integration test with real scenarios',
  description: 'Test logging in real usage scenarios',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior QA engineer',
      task: 'Test logging in realistic scenarios with actual HTTP/MCP calls',
      context: {
        targetQuality: args.targetQuality,
        currentQuality: args.currentQuality,
        scenarios: [
          'Make a DataDog API call and verify request/response are logged',
          'Simulate agent execution and verify MCP calls are logged',
          'Check log output format matches design',
          'Verify no sensitive data (API keys) in logs'
        ]
      },
      instructions: [
        'Run integration tests or create small test scripts',
        'Capture log output and verify it contains expected information',
        'Check that HTTP request bodies are logged with full JSON',
        'Check that HTTP responses are logged',
        'Check that MCP tool calls are logged with tool name and params',
        'Verify log levels work correctly (DEBUG vs INFO)',
        'Return summary of integration test results'
      ],
      outputFormat: 'JSON with passed (boolean), scenarios (array of results), issues (array), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['passed', 'summary'],
      properties: {
        passed: { type: 'boolean' },
        scenarios: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              passed: { type: 'boolean' }
            }
          }
        },
        issues: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['integration', 'testing']
}));

export const finalVerificationTask = defineTask('final-verification', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Final verification',
  description: 'Verify all logging is complete and correct',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior code reviewer',
      task: 'Verify HTTP/MCP logging implementation is production-ready',
      context: {
        targetQuality: args.targetQuality,
        currentQuality: args.currentQuality,
        converged: args.converged,
        integrationResult: args.integrationResult
      },
      instructions: [
        'Review all modified files',
        'Verify DataDog API HTTP calls are logged (body, headers, URL)',
        'Verify MCP tool calls are logged',
        'Verify log format is correct and structured',
        'Verify no sensitive data is logged',
        'Run final test suite to confirm everything passes',
        'Check integration test results',
        'Provide final verdict on production readiness'
      ],
      outputFormat: 'JSON with verified (boolean), verdict (string), issues (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['verified', 'verdict'],
      properties: {
        verified: { type: 'boolean' },
        verdict: { type: 'string' },
        issues: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['verification', 'final']
}));
