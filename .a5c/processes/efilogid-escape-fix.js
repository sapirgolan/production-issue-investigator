/**
 * @process efilogid-escape-fix
 * @description Fix DataDog API efilogid query escaping with TDD quality gate
 * @inputs { targetQuality: number }
 * @outputs { success: boolean, finalQuality: number }
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * Fix efilogid Query Escaping Process
 *
 * Changes the DataDog API efilogid query format from:
 *   @efilogid:{efilogid}
 * To:
 *   @efilogid:"{efilogid}"
 *
 * Uses TDD approach with quality convergence loop.
 */
export async function process(inputs, ctx) {
  const { targetQuality = 90 } = inputs;

  // ============================================================================
  // PHASE 1: WRITE TEST FOR NEW BEHAVIOR
  // ============================================================================

  const testResult = await ctx.task(writeEfilogidTestTask, {
    description: 'Write test for escaped efilogid query format'
  });

  // ============================================================================
  // PHASE 2: IMPLEMENT THE FIX
  // ============================================================================

  const implementResult = await ctx.task(implementEfilogidFixTask, {
    description: 'Update build_efilogid_query to escape with quotes',
    testResult
  });

  // ============================================================================
  // PHASE 3: RUN TESTS AND QUALITY GATE
  // ============================================================================

  let iteration = 0;
  let currentQuality = 0;
  let converged = false;
  const maxIterations = 3;

  while (iteration < maxIterations && !converged) {
    iteration++;

    // Run tests
    const runTestsResult = await ctx.task(runTestsAndCoverageTask, {
      iteration,
      targetQuality
    });

    currentQuality = runTestsResult.qualityScore;

    if (currentQuality >= targetQuality) {
      converged = true;
    } else if (iteration < maxIterations) {
      // Refine implementation
      await ctx.task(refineImplementationTask, {
        iteration,
        feedback: runTestsResult.feedback,
        targetQuality
      });
    }
  }

  // ============================================================================
  // PHASE 4: FINAL VERIFICATION
  // ============================================================================

  const finalVerification = await ctx.task(finalVerificationTask, {
    targetQuality,
    currentQuality,
    converged
  });

  // Breakpoint for approval if converged
  if (converged) {
    await ctx.breakpoint({
      question: `Quality score ${currentQuality}% meets target ${targetQuality}%. Approve the changes?`,
      title: 'Final Approval',
      context: { runId: ctx.runId }
    });
  }

  return {
    success: converged,
    iterations: iteration,
    finalQuality: currentQuality,
    targetQuality,
    verification: finalVerification
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const writeEfilogidTestTask = defineTask('write-efilogid-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Write test for escaped efilogid query',
  description: 'Create test case for build_efilogid_query with escaped quotes',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Write a test case for the build_efilogid_query method that verifies the efilogid value is escaped with quotes',
      context: {
        file: 'utils/datadog_api.py',
        method: 'build_efilogid_query',
        currentBehavior: '@efilogid:{efilogid}',
        expectedBehavior: '@efilogid:"{efilogid}"',
        testFile: 'tests/test_datadog_api_coverage.py'
      },
      instructions: [
        'Read the existing test file tests/test_datadog_api_coverage.py',
        'Add a new test method test_build_efilogid_query_escapes_value that verifies:',
        '  - The query starts with @efilogid:',
        '  - The efilogid value is wrapped in escaped quotes',
        '  - Example: efilogid "-1-abc123" should produce @efilogid:\\"-1-abc123\\"',
        'Use unittest.TestCase style matching existing tests',
        'Return summary of what was done'
      ],
      outputFormat: 'JSON with testAdded (boolean), testMethod (string), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['testAdded', 'summary'],
      properties: {
        testAdded: { type: 'boolean' },
        testMethod: { type: 'string' },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['test', 'tdd']
}));

export const implementEfilogidFixTask = defineTask('implement-efilogid-fix', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement efilogid escaping fix',
  description: 'Update build_efilogid_query to escape efilogid with quotes',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Fix the build_efilogid_query method to escape the efilogid value with quotes',
      context: {
        file: 'utils/datadog_api.py',
        method: 'build_efilogid_query',
        currentCode: 'return f"@efilogid:{efilogid}"',
        expectedCode: 'return f\'@efilogid:\\"{efilogid}\\"\'',
        reason: 'DataDog API requires efilogid values to be quoted when they contain special characters'
      },
      instructions: [
        'Read utils/datadog_api.py',
        'Find the build_efilogid_query method (around line 466-475)',
        'Change the return statement to escape the efilogid with backslash-quotes',
        'The format should be: @efilogid:\\"value\\" (with escaped double quotes)',
        'Return summary of what was changed'
      ],
      outputFormat: 'JSON with implemented (boolean), fileModified (string), summary (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['implemented', 'summary'],
      properties: {
        implemented: { type: 'boolean' },
        fileModified: { type: 'string' },
        summary: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['implementation', 'fix']
}));

export const runTestsAndCoverageTask = defineTask('run-tests-coverage', (args, taskCtx) => ({
  kind: 'agent',
  title: `Run tests and check coverage (iteration ${args.iteration})`,
  description: 'Execute test suite and verify quality score meets target',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior QA engineer',
      task: 'Run tests and calculate quality score based on test results and coverage',
      context: {
        iteration: args.iteration,
        targetQuality: args.targetQuality,
        testCommand: 'uv run python -m pytest tests/test_datadog_api_coverage.py -v --tb=short',
        coverageCommand: 'uv run python -m pytest tests/ --cov=utils/datadog_api --cov-report=term-missing'
      },
      instructions: [
        'Run the test suite using pytest',
        'Run coverage analysis',
        'Calculate quality score based on: tests passing (50%), coverage percentage (50%)',
        'Quality score = (pass_rate * 0.5) + (coverage_rate * 0.5)',
        'Provide feedback if quality is below target',
        'Return the quality score and any issues found'
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
  description: 'Fix issues found in previous iteration',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior Python developer',
      task: 'Fix issues identified in the previous test run',
      context: {
        iteration: args.iteration,
        feedback: args.feedback,
        targetQuality: args.targetQuality
      },
      instructions: [
        'Analyze the feedback from the previous iteration',
        'Fix any failing tests',
        'Improve coverage if needed',
        'Ensure the efilogid escaping is correct',
        'Return summary of refinements made'
      ],
      outputFormat: 'JSON with refined (boolean), changes (array of strings), summary (string)'
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

export const finalVerificationTask = defineTask('final-verification', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Final verification',
  description: 'Verify all changes are correct and complete',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'senior code reviewer',
      task: 'Verify the efilogid escaping fix is complete and correct',
      context: {
        targetQuality: args.targetQuality,
        currentQuality: args.currentQuality,
        converged: args.converged
      },
      instructions: [
        'Read utils/datadog_api.py and verify build_efilogid_query is correctly implemented',
        'Read tests/test_datadog_api_coverage.py and verify test exists for the new behavior',
        'Run final test to confirm everything passes',
        'Provide final verdict on whether the fix is production-ready'
      ],
      outputFormat: 'JSON with verified (boolean), verdict (string), issues (array of strings)'
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
