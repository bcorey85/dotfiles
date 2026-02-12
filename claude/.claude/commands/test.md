---
description: Smart test writer — dispatches the right coder subagent to write tests
allowed-tools: [Task, Read, Glob, Grep]
---

# Test

Analyze what needs testing, determine whether it's frontend or backend, and dispatch the appropriate coder subagent(s).

## Modifiers

- `+fast` — Use Haiku model for coder subagents. Use for simple unit tests with straightforward assertions.
- `+deep` — Use Opus model for coder subagents. Use for complex test scenarios, tricky mocking setups, or comprehensive integration tests.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Analyze the testing target** described below:
   - Read the referenced files to understand what needs testing
   - Determine if this is **frontend** (components, pages, stores, composables → Vitest) or **backend** (models, views, serializers, tasks → Django test framework) or **both**

3. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Task tool calls

   For each coder:
   - Pass the test target description and any relevant context you gathered
   - Instruct it to: examine existing test patterns in the codebase, write tests that follow those patterns, cover happy paths, edge cases, and error scenarios
   - For backend: use Django's test framework
   - For frontend: use Vitest

4. **After coder(s) complete**, summarize:
   - What tests were written
   - What coverage was added
   - Any gaps or follow-up testing needed

## What to test

$ARGUMENTS
