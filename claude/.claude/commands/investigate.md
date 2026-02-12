---
description: Read-only diagnosis — explore an issue without making any changes
allowed-tools: [Task, Read, Glob, Grep]
---

# Investigate

Dispatch an Explore agent to dig into an issue, trace data flow, read code, and report findings. **No files are modified.**

## Modifiers

- `+fast` — Use Haiku model for a quick surface-level scan. Use when you just need to locate something or get a quick answer.
- `+deep` — Use Opus model for a very thorough exploration. Use for subtle bugs, complex data flows, or when initial investigation didn't find the root cause.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to the Task tool call below and set thoroughness to `"very thorough"`. If `+fast` is present, pass `model: "haiku"` and set thoroughness to `"quick"`. Default (no modifier) uses `"medium"` thoroughness. Strip modifiers from the prompt.

2. **Launch an Explore agent** (`subagent_type: Explore`):
   - Pass the issue description below
   - Set thoroughness to `"very thorough"` if `+deep` is specified, otherwise `"medium"`
   - Instruct it to:
     - Trace the relevant code paths
     - Identify the root cause or likely candidates
     - Note any related code that might be affected
     - Document the data flow from entry point to where the issue manifests
   - **Explicitly instruct it NOT to edit or write any files** — this is a read-only investigation

3. **Present findings** to the user:
   - Root cause (confirmed or suspected)
   - Relevant file paths and line numbers
   - Data flow / call chain
   - Suggested fix approach (without implementing it)
   - Recommend the appropriate next command: `/fix`, `/be-fix`, `/fe-fix`, `/fs-fix`, or a `-plan` command if architectural

## Issue

$ARGUMENTS
