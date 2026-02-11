/**
 * @process stack-trace-implementation
 * @description Implement stack trace extraction and analysis for Production Issue Investigator
 * @inputs { planPath: string }
 * @outputs { success: boolean, filesCreated: array, filesModified: array, testsResults: object }
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * Stack Trace Implementation Process
 *
 * Implements the 5-phase plan from docs/iridescent-pondering-salamander.md:
 * Phase 1: Add Stack Trace to LogEntry (utils/datadog_api.py)
 * Phase 2: Create Stack Trace Parser (utils/stack_trace_parser.py)
 * Phase 3: Update Main Agent (agents/main_agent.py)
 * Phase 4: Enhance Code Checker (agents/code_checker.py)
 * Phase 5: Update Report Generator (utils/report_generator.py)
 */
export async function process(inputs, ctx) {
  const { planPath = 'docs/iridescent-pondering-salamander.md' } = inputs;

  // ============================================================================
  // PHASE 1: ADD STACK TRACE TO LOGENTRY
  // ============================================================================

  const phase1Result = await ctx.task(implementPhase1Task, {
    phase: 1,
    description: 'Add stack_trace field to LogEntry and extract in _extract_log_entry()',
    targetFile: 'utils/datadog_api.py'
  });

  await ctx.breakpoint({
    question: `Phase 1 complete: Added stack_trace field to LogEntry. Verify the changes look correct?`,
    title: 'Phase 1: LogEntry Update',
    context: {
      runId: ctx.runId,
      files: [
        { path: 'utils/datadog_api.py', format: 'python', label: 'DataDog API' }
      ]
    }
  });

  // ============================================================================
  // PHASE 2: CREATE STACK TRACE PARSER
  // ============================================================================

  const phase2Result = await ctx.task(implementPhase2Task, {
    phase: 2,
    description: 'Create utils/stack_trace_parser.py with StackFrame, ParsedStackTrace, StackTraceParser classes',
    targetFile: 'utils/stack_trace_parser.py'
  });

  // Run tests for the new parser
  const phase2TestResult = await ctx.task(runTestsTask, {
    testFile: 'tests/test_stack_trace_parser.py',
    description: 'Test stack trace parser functionality'
  });

  await ctx.breakpoint({
    question: `Phase 2 complete: Created stack trace parser. Tests ${phase2TestResult.passed ? 'PASSED' : 'FAILED'}. Continue to Phase 3?`,
    title: 'Phase 2: Stack Trace Parser',
    context: {
      runId: ctx.runId,
      files: [
        { path: 'utils/stack_trace_parser.py', format: 'python', label: 'Stack Trace Parser' },
        { path: 'tests/test_stack_trace_parser.py', format: 'python', label: 'Parser Tests' }
      ]
    }
  });

  // ============================================================================
  // PHASE 3: UPDATE MAIN AGENT
  // ============================================================================

  const phase3Result = await ctx.task(implementPhase3Task, {
    phase: 3,
    description: 'Add _extract_stack_trace_files_per_service() and integrate into investigation flow',
    targetFile: 'agents/main_agent.py'
  });

  await ctx.breakpoint({
    question: `Phase 3 complete: Updated main agent with stack trace extraction. Verify integration looks correct?`,
    title: 'Phase 3: Main Agent Update',
    context: {
      runId: ctx.runId,
      files: [
        { path: 'agents/main_agent.py', format: 'python', label: 'Main Agent' }
      ]
    }
  });

  // ============================================================================
  // PHASE 4: ENHANCE CODE CHECKER
  // ============================================================================

  const phase4Result = await ctx.task(implementPhase4Task, {
    phase: 4,
    description: 'Add Kotlin/Java fallback in analyze_files_directly()',
    targetFile: 'agents/code_checker.py'
  });

  await ctx.breakpoint({
    question: `Phase 4 complete: Enhanced code checker with Kotlin/Java fallback. Verify changes?`,
    title: 'Phase 4: Code Checker Enhancement',
    context: {
      runId: ctx.runId,
      files: [
        { path: 'agents/code_checker.py', format: 'python', label: 'Code Checker' }
      ]
    }
  });

  // ============================================================================
  // PHASE 5: UPDATE REPORT GENERATOR
  // ============================================================================

  const phase5Result = await ctx.task(implementPhase5Task, {
    phase: 5,
    description: 'Add Stack Trace Analysis section to report',
    targetFile: 'utils/report_generator.py'
  });

  await ctx.breakpoint({
    question: `Phase 5 complete: Updated report generator. All phases complete. Run final verification?`,
    title: 'Phase 5: Report Generator Update',
    context: {
      runId: ctx.runId,
      files: [
        { path: 'utils/report_generator.py', format: 'python', label: 'Report Generator' }
      ]
    }
  });

  // ============================================================================
  // FINAL VERIFICATION
  // ============================================================================

  const verificationResult = await ctx.task(verifyImplementationTask, {
    description: 'Run all tests and verify implementation'
  });

  await ctx.breakpoint({
    question: `Implementation complete! Final verification ${verificationResult.success ? 'PASSED' : 'FAILED'}. Review final results?`,
    title: 'Implementation Complete',
    context: {
      runId: ctx.runId,
      files: [
        { path: 'utils/datadog_api.py', format: 'python', label: 'DataDog API' },
        { path: 'utils/stack_trace_parser.py', format: 'python', label: 'Stack Trace Parser' },
        { path: 'agents/main_agent.py', format: 'python', label: 'Main Agent' },
        { path: 'agents/code_checker.py', format: 'python', label: 'Code Checker' },
        { path: 'utils/report_generator.py', format: 'python', label: 'Report Generator' }
      ]
    }
  });

  return {
    success: verificationResult.success,
    phases: {
      phase1: phase1Result,
      phase2: phase2Result,
      phase3: phase3Result,
      phase4: phase4Result,
      phase5: phase5Result
    },
    verification: verificationResult,
    metadata: {
      processId: 'stack-trace-implementation',
      timestamp: ctx.now()
    }
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

/**
 * Phase 1: Add stack_trace to LogEntry
 */
export const implementPhase1Task = defineTask('implement-phase1', (args, taskCtx) => ({
  kind: 'agent',
  title: `Phase ${args.phase}: Update LogEntry dataclass`,
  description: args.description,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing feature enhancement',
      task: `Implement Phase 1 of the stack trace feature for the Production Issue Investigator.

TASK: Update utils/datadog_api.py to extract stack traces from DataDog logs.

CHANGES REQUIRED:

1. Add field to LogEntry dataclass (around line 59):
   stack_trace: Optional[str] = None

2. Update _extract_log_entry() method to extract stack trace from multiple possible locations:
   - nested_attrs.get("error", {}).get("stack")
   - nested_attrs.get("stack_trace")
   - nested_attrs.get("exception", {}).get("stacktrace")

Read the file first, then make the edits. The dataclass field should be added before raw_attributes.`,
      context: {
        phase: args.phase,
        targetFile: args.targetFile
      },
      instructions: [
        'Read utils/datadog_api.py first',
        'Add stack_trace: Optional[str] = None field to LogEntry dataclass',
        'Update _extract_log_entry() to extract stack trace from error.stack, stack_trace, or exception.stacktrace',
        'Return the stack_trace field in the LogEntry constructor',
        'Do NOT change any other functionality'
      ],
      outputFormat: 'JSON with success boolean, changes made, and any errors'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'changes'],
      properties: {
        success: { type: 'boolean' },
        changes: { type: 'array', items: { type: 'string' } },
        error: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['agent', 'implementation', 'phase-1']
}));

/**
 * Phase 2: Create stack trace parser
 */
export const implementPhase2Task = defineTask('implement-phase2', (args, taskCtx) => ({
  kind: 'agent',
  title: `Phase ${args.phase}: Create Stack Trace Parser`,
  description: args.description,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer creating a new utility module',
      task: `Create utils/stack_trace_parser.py - a parser for Java/Kotlin stack traces.

THE NEW FILE MUST INCLUDE:

1. StackFrame dataclass:
   - class_name: str
   - method_name: str
   - file_name: Optional[str]
   - line_number: Optional[int]
   - is_sunbit: bool
   - to_file_path() method that converts to src/main/kotlin/... or src/main/java/...

2. ParsedStackTrace dataclass:
   - exception_type: Optional[str]
   - exception_message: Optional[str]
   - frames: List[StackFrame]
   - sunbit_frames: List[StackFrame] (filtered to com.sunbit packages)
   - unique_file_paths: Set[str]

3. StackTraceParser class:
   - FRAME_PATTERN regex: r'^\\s*at\\s+([\\w.$]+)\\.([\\w$<>]+)\\(([^:)]+)?(?::(\\d+))?\\)'
   - EXCEPTION_PATTERN regex for exception headers
   - SUNBIT_PACKAGE_PREFIX = 'com.sunbit'
   - parse(stack_trace: str) -> ParsedStackTrace
   - extract_file_paths_from_message(message: str) -> Set[str]

4. Convenience functions:
   - parse_stack_trace(stack_trace: str) -> ParsedStackTrace
   - extract_file_paths(stack_trace: str, message: str = None) -> Set[str]

Handle inner classes (MyService$Companion -> MyService.kt).
Filter to only com.sunbit packages.`,
      context: {
        phase: args.phase,
        targetFile: args.targetFile
      },
      instructions: [
        'Create the new file utils/stack_trace_parser.py',
        'Include all dataclasses and the parser class',
        'Use proper Python typing and dataclasses',
        'Add docstrings for all classes and methods',
        'Follow existing code style from utils/datadog_api.py',
        'Also create tests/test_stack_trace_parser.py with unit tests'
      ],
      outputFormat: 'JSON with success boolean, files created, and any errors'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filesCreated'],
      properties: {
        success: { type: 'boolean' },
        filesCreated: { type: 'array', items: { type: 'string' } },
        error: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['agent', 'implementation', 'phase-2']
}));

/**
 * Phase 3: Update Main Agent
 */
export const implementPhase3Task = defineTask('implement-phase3', (args, taskCtx) => ({
  kind: 'agent',
  title: `Phase ${args.phase}: Update Main Agent`,
  description: args.description,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer updating main orchestration logic',
      task: `Update agents/main_agent.py to extract and use stack trace file paths.

CHANGES REQUIRED:

1. Add import at top:
   from utils.stack_trace_parser import StackTraceParser, extract_file_paths

2. Add new method _extract_stack_trace_files_per_service(self, dd_result):
   - Iterate through logs
   - For logs with stack_trace, parse and extract file paths
   - Also check message for embedded stack traces (for error/warn logs)
   - Return Dict[str, Set[str]] mapping service -> file paths

3. Update ServiceInvestigationResult dataclass:
   - Add: stack_trace_files: Optional[Set[str]] = None

4. Update investigate() method (after line ~378):
   - Call _extract_stack_trace_files_per_service(dd_result)
   - Pass result to _investigate_services_parallel()

5. Update _investigate_services_parallel():
   - Add service_stack_trace_files parameter
   - Pass to _investigate_single_service()

6. Update _investigate_single_service():
   - Add stack_trace_files parameter
   - After logger-based analysis, call code_checker.analyze_files_directly() with stack trace files
   - Deduplicate: exclude files already analyzed via logger_names
   - Merge FileAnalysis results

7. Add helper methods:
   - _get_repo_for_service(self, service_name) -> tuple(owner, repo)
   - _extract_commit_hash(self, dd_version) -> str`,
      context: {
        phase: args.phase,
        targetFile: args.targetFile
      },
      instructions: [
        'Read agents/main_agent.py first',
        'Make all required changes as specified',
        'Preserve existing functionality',
        'Follow existing code patterns'
      ],
      outputFormat: 'JSON with success boolean, changes made, and any errors'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'changes'],
      properties: {
        success: { type: 'boolean' },
        changes: { type: 'array', items: { type: 'string' } },
        error: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['agent', 'implementation', 'phase-3']
}));

/**
 * Phase 4: Enhance Code Checker
 */
export const implementPhase4Task = defineTask('implement-phase4', (args, taskCtx) => ({
  kind: 'agent',
  title: `Phase ${args.phase}: Enhance Code Checker`,
  description: args.description,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer enhancing existing module',
      task: `Update agents/code_checker.py to try alternative file extensions.

CHANGE REQUIRED:

Update analyze_files_directly() method to:
- When file not found at exact path, try alternative extension
- If path ends with .kt, also try .java equivalent (src/main/java/...)
- If path ends with .java, also try .kt equivalent (src/main/kotlin/...)
- Update file_analysis.file_path to the actual found path

The method already exists (lines 920-990). Enhance the file fetching logic to try both extensions.`,
      context: {
        phase: args.phase,
        targetFile: args.targetFile
      },
      instructions: [
        'Read agents/code_checker.py first',
        'Update analyze_files_directly() method',
        'Add fallback logic for .kt <-> .java',
        'Keep all existing functionality'
      ],
      outputFormat: 'JSON with success boolean, changes made, and any errors'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'changes'],
      properties: {
        success: { type: 'boolean' },
        changes: { type: 'array', items: { type: 'string' } },
        error: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['agent', 'implementation', 'phase-4']
}));

/**
 * Phase 5: Update Report Generator
 */
export const implementPhase5Task = defineTask('implement-phase5', (args, taskCtx) => ({
  kind: 'agent',
  title: `Phase ${args.phase}: Update Report Generator`,
  description: args.description,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer updating report generation',
      task: `Update utils/report_generator.py to include stack trace analysis in reports.

CHANGE REQUIRED:

Add a "Stack Trace Analysis" section to the evidence section of reports:
- List files discovered from stack traces per service
- Show which files were analyzed
- Only include section if stack trace files were found`,
      context: {
        phase: args.phase,
        targetFile: args.targetFile
      },
      instructions: [
        'Read utils/report_generator.py first',
        'Add Stack Trace Analysis section to evidence',
        'Follow existing report format patterns'
      ],
      outputFormat: 'JSON with success boolean, changes made, and any errors'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'changes'],
      properties: {
        success: { type: 'boolean' },
        changes: { type: 'array', items: { type: 'string' } },
        error: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['agent', 'implementation', 'phase-5']
}));

/**
 * Run tests task
 */
export const runTestsTask = defineTask('run-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: `Run tests: ${args.testFile}`,
  description: args.description,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Test runner',
      task: `Run the tests using: uv run pytest ${args.testFile} -v`,
      context: { testFile: args.testFile },
      instructions: [
        'Run the pytest command',
        'Capture output',
        'Report pass/fail status'
      ],
      outputFormat: 'JSON with passed boolean and output'
    },
    outputSchema: {
      type: 'object',
      required: ['passed', 'output'],
      properties: {
        passed: { type: 'boolean' },
        output: { type: 'string' },
        failedTests: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['agent', 'testing']
}));

/**
 * Verify implementation task
 */
export const verifyImplementationTask = defineTask('verify-implementation', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify Implementation',
  description: args.description,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer verifying implementation',
      task: `Verify the stack trace implementation is complete and working.

Run these verification steps:
1. Run: uv run pytest tests/test_stack_trace_parser.py -v
2. Verify all 5 files were modified/created:
   - utils/datadog_api.py (has stack_trace field)
   - utils/stack_trace_parser.py (new file exists)
   - agents/main_agent.py (has _extract_stack_trace_files_per_service)
   - agents/code_checker.py (has Kotlin/Java fallback)
   - utils/report_generator.py (has stack trace section)
3. Check for any syntax errors`,
      context: {},
      instructions: [
        'Run all verification steps',
        'Report overall success/failure',
        'List any issues found'
      ],
      outputFormat: 'JSON with success boolean and details'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'checks'],
      properties: {
        success: { type: 'boolean' },
        checks: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              passed: { type: 'boolean' },
              details: { type: 'string' }
            }
          }
        },
        issues: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['agent', 'verification']
}));
