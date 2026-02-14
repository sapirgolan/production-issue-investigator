/**
 * @process mcp-tools-fix
 * @description Fix JSON serialization error by decorating MCP tools with @tool decorator
 * @inputs { specificationFile: string, projectRoot: string }
 * @outputs { success: boolean, phases: object, qualityReport: object }
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * MCP Tools Fix Process
 *
 * Fixes the JSON serialization error by decorating MCP tools with @tool decorator
 * and using create_sdk_mcp_server() wrapper across all 5 phases.
 *
 * Based on: docs/MCP_TOOLS_FIX_SPECIFICATION.md
 */

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

// Phase 0: Review
const reviewTask = defineTask('review-before-proceed', (args, taskCtx) => ({
  kind: 'breakpoint',
  title: 'Review implementation plan',
  breakpoint: {
    question: 'Ready to implement MCP tools fix across 5 phases with 10 tasks. Review the specification and approve to proceed.',
    context: {
      specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md',
      phases: [
        'Phase 1: DataDog Server (3 tasks)',
        'Phase 2: GitHub Server (3 tasks)',
        'Phase 3: Lead Agent (3 tasks)',
        'Phase 4: Tests (1 task)',
        'Phase 5: Verification (4 tasks)'
      ],
      files: [
        'mcp_servers/datadog_server.py',
        'mcp_servers/github_server.py',
        'agents/lead_agent.py',
        'tests/test_lead_agent.py'
      ]
    },
    title: 'Approve MCP Tools Fix Implementation'
  },
  io: {
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

// Phase 1: DataDog Server
const addDataDogImportsTask = defineTask('add-datadog-imports', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Add SDK imports to DataDog server',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Add SDK imports to mcp_servers/datadog_server.py',
      context: {
        file: 'mcp_servers/datadog_server.py',
        location: 'After existing imports, around line 28',
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 1)',
        'Read the current mcp_servers/datadog_server.py file',
        'Add the following imports after existing imports (around line 28):',
        '  from claude_agent_sdk import tool, create_sdk_mcp_server',
        'Verify no syntax errors by reading the file back',
        'Return success status'
      ],
      outputFormat: 'JSON with {success: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'message'],
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const decorateDataDogToolsTask = defineTask('decorate-datadog-tools', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Decorate DataDog tools with @tool decorator',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Decorate all 3 DataDog tools with @tool decorator',
      context: {
        file: 'mcp_servers/datadog_server.py',
        tools: ['search_logs_tool', 'get_logs_by_efilogid_tool', 'parse_stack_trace_tool'],
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 2.1, 2.2, 2.3)',
        'Read mcp_servers/datadog_server.py',
        'Add @tool decorator before search_logs_tool (line 157) with exact parameters from spec',
        'Add @tool decorator before get_logs_by_efilogid_tool (line 230) with exact parameters from spec',
        'Add @tool decorator before parse_stack_trace_tool (line 305) with exact parameters from spec',
        'Verify the function signatures remain unchanged',
        'Verify no syntax errors',
        'Return success status with list of decorated tools'
      ],
      outputFormat: 'JSON with {success: boolean, decoratedTools: string[], message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'decoratedTools', 'message'],
      properties: {
        success: { type: 'boolean' },
        decoratedTools: { type: 'array', items: { type: 'string' } },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const createDataDogServerTask = defineTask('create-datadog-server', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create DataDog MCP server instance',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Create DATADOG_MCP_SERVER instance at end of file',
      context: {
        file: 'mcp_servers/datadog_server.py',
        location: 'End of file, around line 396',
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 3)',
        'Read mcp_servers/datadog_server.py',
        'Add DATADOG_MCP_SERVER export at the END of the file',
        'Use exact code from Task 3 in specification',
        'Keep existing utility functions (reset_datadog_api, set_datadog_api, etc.) untouched',
        'Verify no syntax errors',
        'Return success status'
      ],
      outputFormat: 'JSON with {success: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'message'],
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

// Phase 2: GitHub Server
const addGitHubImportsTask = defineTask('add-github-imports', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Add SDK imports to GitHub server',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Add SDK imports to mcp_servers/github_server.py',
      context: {
        file: 'mcp_servers/github_server.py',
        location: 'After existing imports, around line 28',
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 4)',
        'Read mcp_servers/github_server.py',
        'Add the following imports after existing imports (around line 28):',
        '  from claude_agent_sdk import tool, create_sdk_mcp_server',
        'Verify no syntax errors',
        'Return success status'
      ],
      outputFormat: 'JSON with {success: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'message'],
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const decorateGitHubToolsTask = defineTask('decorate-github-tools', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Decorate GitHub tools with @tool decorator',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Decorate all 4 GitHub tools with @tool decorator',
      context: {
        file: 'mcp_servers/github_server.py',
        tools: ['search_commits_tool', 'get_file_content_tool', 'get_pr_files_tool', 'compare_commits_tool'],
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 5.1, 5.2, 5.3, 5.4)',
        'Read mcp_servers/github_server.py',
        'Add @tool decorator before search_commits_tool (line 153) with exact parameters from spec',
        'Add @tool decorator before get_file_content_tool (line 249) with exact parameters from spec',
        'Add @tool decorator before get_pr_files_tool (line 326) with exact parameters from spec',
        'Add @tool decorator before compare_commits_tool (line 403) with exact parameters from spec',
        'Verify function signatures remain unchanged',
        'Verify no syntax errors',
        'Return success status with list of decorated tools'
      ],
      outputFormat: 'JSON with {success: boolean, decoratedTools: string[], message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'decoratedTools', 'message'],
      properties: {
        success: { type: 'boolean' },
        decoratedTools: { type: 'array', items: { type: 'string' } },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const createGitHubServerTask = defineTask('create-github-server', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create GitHub MCP server instance',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Create GITHUB_MCP_SERVER instance at end of file',
      context: {
        file: 'mcp_servers/github_server.py',
        location: 'End of file, around line 500+',
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 6)',
        'Read mcp_servers/github_server.py',
        'Add GITHUB_MCP_SERVER export at the END of the file',
        'Use exact code from Task 6 in specification',
        'Keep existing utility functions (reset_github_helper, set_github_helper, etc.) untouched',
        'Verify no syntax errors',
        'Return success status'
      ],
      outputFormat: 'JSON with {success: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'message'],
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

// Phase 3: Lead Agent
const updateLeadAgentImportsTask = defineTask('update-lead-agent-imports', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update Lead Agent imports',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Update imports in agents/lead_agent.py',
      context: {
        file: 'agents/lead_agent.py',
        location: 'Lines 32-33',
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 7)',
        'Read agents/lead_agent.py',
        'Replace lines 32-33 with new imports:',
        '  from mcp_servers.datadog_server import DATADOG_MCP_SERVER',
        '  from mcp_servers.github_server import GITHUB_MCP_SERVER',
        'Verify imports resolve without errors',
        'Return success status'
      ],
      outputFormat: 'JSON with {success: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'message'],
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const removeManualServerDefsTask = defineTask('remove-manual-server-defs', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Remove manual MCP server definitions',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Remove manual server dictionaries from agents/lead_agent.py',
      context: {
        file: 'agents/lead_agent.py',
        location: 'Lines 37-59',
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 8)',
        'Read agents/lead_agent.py',
        'DELETE lines 37-59 (entire datadog_mcp_server and github_mcp_server dicts)',
        'Verify no references remain except in registration section',
        'Verify no syntax errors',
        'Return success status'
      ],
      outputFormat: 'JSON with {success: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'message'],
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const updateServerRegistrationTask = defineTask('update-server-registration', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update MCP server registration',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Update MCP server registration in agents/lead_agent.py',
      context: {
        file: 'agents/lead_agent.py',
        location: 'Lines 223-226 (inside investigate() method)',
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 9)',
        'Read agents/lead_agent.py',
        'Find the mcp_servers dict around line 223-226',
        'Replace variable names to use DATADOG_MCP_SERVER and GITHUB_MCP_SERVER',
        'Update comment to mention SDK-wrapped instances',
        'Verify variables reference the imported constants',
        'Return success status'
      ],
      outputFormat: 'JSON with {success: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'message'],
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

// Phase 4: Tests
const updateTestPatchesTask = defineTask('update-test-patches', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update test_lead_agent.py patches',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer implementing Claude Agent SDK MCP tools',
      task: 'Update patch names in tests/test_lead_agent.py',
      context: {
        file: 'tests/test_lead_agent.py',
        location: 'Lines 878-879',
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Task 10)',
        'Read tests/test_lead_agent.py',
        'Find line 878-879 in test_lead_agent_configures_mcp_servers',
        'Replace patch names from datadog_mcp_server to DATADOG_MCP_SERVER',
        'Replace patch names from github_mcp_server to GITHUB_MCP_SERVER',
        'Verify no syntax errors',
        'Return success status'
      ],
      outputFormat: 'JSON with {success: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'message'],
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

// Phase 5: Verification
const runMcpToolsTestsTask = defineTask('run-mcp-tools-tests', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Run test_mcp_tools.py',
  shell: {
    command: 'uv run python -m pytest tests/test_mcp_tools.py -v',
    workingDirectory: '/Users/sapirgolan/workspace/production-issue-investigator',
    captureStdout: true,
    captureStderr: true
  },
  io: {
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const runLeadAgentTestsTask = defineTask('run-lead-agent-tests', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Run test_lead_agent.py',
  shell: {
    command: 'uv run python -m pytest tests/test_lead_agent.py -v',
    workingDirectory: '/Users/sapirgolan/workspace/production-issue-investigator',
    captureStdout: true,
    captureStderr: true
  },
  io: {
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const runAllTestsTask = defineTask('run-all-tests', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Run all tests with coverage',
  shell: {
    command: 'uv run python -m pytest tests/ -v --cov=mcp_servers --cov=utils --cov-report=term-missing',
    workingDirectory: '/Users/sapirgolan/workspace/production-issue-investigator',
    captureStdout: true,
    captureStderr: true
  },
  io: {
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const verifyApplicationStartsTask = defineTask('verify-application-starts', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify application starts without error',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA engineer verifying application startup',
      task: 'Verify the application starts without JSON serialization error',
      context: {
        specification: 'docs/MCP_TOOLS_FIX_SPECIFICATION.md'
      },
      instructions: [
        'Read the specification document (Manual Verification section)',
        'Attempt to run: echo "test" | timeout 10 uv run main.py',
        'Check for JSON serialization error in output',
        'If error occurs, return failure with error details',
        'If no error and application starts, return success',
        'The success criteria is NO "TypeError: Object of type function is not JSON serializable"'
      ],
      outputFormat: 'JSON with {success: boolean, startupSuccessful: boolean, errorFound: boolean, message: string}'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'startupSuccessful', 'errorFound', 'message'],
      properties: {
        success: { type: 'boolean' },
        startupSuccessful: { type: 'boolean' },
        errorFound: { type: 'boolean' },
        message: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

//============================================================================
// MAIN PROCESS
// ============================================================================

export async function process(inputs, ctx) {
  const specFile = inputs.specificationFile || 'docs/MCP_TOOLS_FIX_SPECIFICATION.md';
  const projectRoot = inputs.projectRoot || '/Users/sapirgolan/workspace/production-issue-investigator';

  // Phase 0: Review plan
  await ctx.breakpoint({
    question: 'Ready to implement MCP tools fix across 5 phases with 10 tasks. Review the specification and approve to proceed.',
    title: 'Approve MCP Tools Fix Implementation',
    context: {
      specification: specFile,
      phases: [
        'Phase 1: DataDog Server (3 tasks)',
        'Phase 2: GitHub Server (3 tasks)',
        'Phase 3: Lead Agent (3 tasks)',
        'Phase 4: Tests (1 task)',
        'Phase 5: Verification (4 tasks)'
      ],
      files: [
        'mcp_servers/datadog_server.py',
        'mcp_servers/github_server.py',
        'agents/lead_agent.py',
        'tests/test_lead_agent.py'
      ]
    }
  });

  // Phase 1: DataDog Server
  const task1 = await ctx.task(addDataDogImportsTask, { specFile });
  const task2 = await ctx.task(decorateDataDogToolsTask, { specFile });
  const task3 = await ctx.task(createDataDogServerTask, { specFile });

  // Phase 2: GitHub Server
  const task4 = await ctx.task(addGitHubImportsTask, { specFile });
  const task5 = await ctx.task(decorateGitHubToolsTask, { specFile });
  const task6 = await ctx.task(createGitHubServerTask, { specFile });

  // Phase 3: Lead Agent
  const task7 = await ctx.task(updateLeadAgentImportsTask, { specFile });
  const task8 = await ctx.task(removeManualServerDefsTask, { specFile });
  const task9 = await ctx.task(updateServerRegistrationTask, { specFile });

  // Phase 4: Tests
  const task10 = await ctx.task(updateTestPatchesTask, { specFile });

  // Phase 5: Verification (run tests in parallel)
  const mcpTests = await ctx.task(runMcpToolsTestsTask, { specFile });
  const leadTests = await ctx.task(runLeadAgentTestsTask, { specFile });
  const allTests = await ctx.task(runAllTestsTask, { specFile });
  const appStartup = await ctx.task(verifyApplicationStartsTask, { specFile });

  return {
    status: 'success',
    phases: {
      phase1: { task1, task2, task3 },
      phase2: { task4, task5, task6 },
      phase3: { task7, task8, task9 },
      phase4: { task10 },
      phase5: { mcpTests, leadTests, allTests, appStartup }
    },
    message: 'MCP tools fix completed across all 5 phases'
  };
}
