---
description: Peer-review recent changes using the code-reviewer subagent
allowed-tools: [Task, Bash, Read, Glob, Grep]
---

# Code Review

Review recent changes in this codebase using the code-reviewer subagent.

## Modifiers

- `+fast` — Use Haiku model for code-reviewer subagent(s). Use for quick sanity checks on small changes.
- `+deep` — Use Opus model for code-reviewer subagent(s). Use for security-sensitive changes, complex logic, or architectural modifications.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`.

2. **Check the number of modified files**:
   ```bash
   git diff --name-only HEAD 2>/dev/null | wc -l
   ```
   Include staged files: `git diff --cached --name-only 2>/dev/null`

3. **Dispatch code-reviewer subagent(s)**:

   **If 5 or fewer files changed**: Dispatch a single code-reviewer subagent

   **If more than 5 files changed**: Dispatch parallel code-reviewer subagents to speed up the process:
   - One for frontend files (components, pages, stores, styles, etc.)
   - One for backend files (models, controllers/views, services, migrations, tests, etc.)

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

4. **Present the review results** to the user organized by severity

5. **Suggest next steps** based on the review outcome:
   - **If issues found**: "Run `/fix-feedback` to fix these issues, then `/peer-review` again to verify the fixes."
   - **If all clear**: "No issues found. Ready for `/commit`."

## Arguments

$ARGUMENTS
