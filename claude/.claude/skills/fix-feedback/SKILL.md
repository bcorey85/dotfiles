---
name: fix-feedback
description: Dispatch coder subagents to fix review feedback, then auto-run peer review
allowed-tools: [Task, Read, Glob, Grep, Skill]
---

# Fix Code Review Feedback

Dispatch parallel frontend-coder and backend-coder subagents to investigate and resolve valid issues from the most recent code review.

## Modifiers

- `+fast` — Use Haiku model for coder subagents. Use when review findings are trivial (typos, simple style fixes).
- `+deep` — Use Opus model for coder subagents. Use for complex review findings that require deeper reasoning to fix correctly.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt.

2. **Parse the review feedback** from the conversation to categorize issues as frontend or backend

3. **Launch coder agents in parallel** using a single message with multiple Task tool calls:

   **Frontend Coder** (`subagent_type: frontend-coder`):
   - Pass all frontend-specific issues with file paths and line numbers
   - Instruct the agent to investigate and fix each valid issue
   - Include enough context from the review for the coder to understand the problem

   **Backend Coder** (`subagent_type: backend-coder`):
   - Pass all backend-specific issues with file paths and line numbers
   - Instruct the agent to investigate and fix each valid issue
   - Include enough context from the review for the coder to understand the problem
   - Instruct the agent: "After fixing each issue, check all callers and consumers of the changed code. If a fix changes a method signature, return type, or behavioral contract, update every caller in the same pass. Do not leave callers out of sync."

   If all issues are frontend-only or backend-only, launch only the relevant coder agent.

4. **After coders complete**, summarize:
   - Which issues were fixed
   - Any issues intentionally skipped (with reasoning)
   - Any new concerns discovered
   - If any issue requires architectural rethinking, recommend the user run `/eng-plan` instead

5. **Auto-dispatch peer review**: After summarizing the fixes, tell the user: "Auto-dispatching `/peer-review` to verify the fixes before committing." Then invoke the `/peer-review` skill using the Skill tool (`skill: "peer-review"`). If the user passed `+fast` or `+deep`, pass the same modifier to the peer review invocation (e.g., `skill: "peer-review", args: "+fast"`). This step runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

## Validation

Each agent should verify issues are valid before fixing. Skip issues that are:
- False positives or stylistic preferences
- Out of scope for a quick fix
- Blocked by other unresolved issues
- Architectural in nature (recommend `/eng-plan` instead)
