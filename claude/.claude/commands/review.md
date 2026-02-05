---
description: Review recent changes using the code-reviewer subagent
allowed-tools: [Task, Bash, Read, Glob, Grep]
---

# Code Review

Review recent changes in this codebase using the code-reviewer subagent.

## Instructions

1. **Check the number of modified files**:
   ```bash
   git diff --name-only HEAD 2>/dev/null | wc -l
   ```
   Include staged files: `git diff --cached --name-only 2>/dev/null`

2. **Dispatch code-reviewer subagent(s)**:

   **If 5 or fewer files changed**: Dispatch a single code-reviewer subagent

   **If more than 5 files changed**: Dispatch parallel code-reviewer subagents to speed up the process:
   - One for frontend files (components, pages, stores, etc.)
   - One for backend files (models, views, serializers, tests, etc.)

   Launch both in a single message with multiple Task tool calls.

   Each reviewer should check for:
   - Bugs or logic errors
   - Security issues
   - Performance problems
   - Code style violations
   - Missing error handling
   - Anti-patterns
   - Architectural violations

   If a file path is provided via $ARGUMENTS, focus the review on that file only.

3. **Present the review results** to the user organized by severity

4. **Remind the user** they can run `/fix-feedback` to dispatch parallel subagents to fix the issues

## Arguments

$ARGUMENTS
