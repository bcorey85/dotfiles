---
type: "Change"
change_type: "changed"
title: "CI runs the script tests when a script under scripts/.local/bin changes"
description: "The script-tests workflow adds scripts/.local/bin/** to its push and pull_request paths, so an edit to herdr-worktree or another stowed script runs its tests in CI."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T13:41:24-05:00"}
seq: 107
kind: "fix"
components: ["script/herdr-worktree", "script/agent-cost"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_script_tests_workflow.py::ScriptTestsWorkflowTest::test_every_stowed_script_under_test_triggers_the_workflow"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `.github/workflows/script-tests.yml` adds `scripts/.local/bin/**` to both its `push` and `pull_request` path lists.

## Evidence

- The review of the herdr-worktree linked-worktree fix found that `tests/scripts/test_herdr_worktree.py` tests
  `scripts/.local/bin/herdr-worktree`, but the workflow ran only on toolkit-script and test paths. A change to the
  script alone ran no CI. `tests/scripts/test_agent_cost.py` tests `scripts/.local/bin/agent-cost` and was uncovered the
  same way.
- `tests/scripts/test_script_tests_workflow.py` reads the workflow's `push` and `pull_request` path lists and fails for
  any script a test file names as `"scripts" / ".local" / "bin" / "<name>"` that no glob covers; it fails on the
  workflow without the new glob (agent-cost and herdr-worktree uncovered).

## Result

- The next push that touches only a script under `scripts/.local/bin` starts the workflow.

## Watch

—

## Back-out

Revert the commit.
