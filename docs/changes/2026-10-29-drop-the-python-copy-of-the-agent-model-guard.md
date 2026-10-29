---
type: "Change"
title: "Drop the Python copy of the agent-model guard"
description: "settings.json registers one agent-model guard on PreToolUse(Agent), the work package's agent-model-guard.sh. The Python port gates/agent_model_guard.py, its test and its fork fixture are deleted."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T18:00:00-05:00"}
seq: 230
kind: "fix"
components: ["script/agent-model-guard", "rule/settings-json"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_agent_hook_registration.py::AgentHookRegistrationTest::test_exactly_one_agent_model_guard_runs_on_agent"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/settings.json`: the `agent_model_guard.py` entry is gone from PreToolUse(Agent). `agent-model-guard.sh` stays, and so does its `WORK_HOOKS` entry.
- Deleted `claude/.claude/scripts/gates/agent_model_guard.py`, `tests/scripts/test_agent_model_guard.py` and `tests/scripts/fixtures/hook_event_agent_fork.json`.
- `tests/scripts/test_review_fixes.py` and `tests/scripts/test_toolkit_self_location.py` drop their entries for the Python guard.
- New `tests/scripts/test_agent_hook_registration.py` pins exactly one agent-model guard on Agent: the `.sh`.

## Evidence

- Both guards ran on every Agent call. The `.sh` denies a fork dispatch, so the fork pass in the Python copy (seq 92) changed nothing. The fork fix is logged against the work package.

## Result

- On the base settings the new test finds two guard commands and fails. On this change it finds one and passes.

## Watch

—

## Back-out

Revert the commit. Both guards run on Agent again.
