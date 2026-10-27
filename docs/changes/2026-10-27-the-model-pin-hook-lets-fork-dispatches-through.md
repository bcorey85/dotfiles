---
type: "Change"
title: "The model-pin hook lets fork dispatches through"
description: "agent_model_guard passes an Agent call with subagent_type fork before its opus, inherit and pin checks, since a fork always runs on the parent's model."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T12:26:06-05:00"}
seq: 90
kind: "fix"
components: ["script/agent-model-guard"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_agent_model_guard.py::AgentModelGuardTest::test_fork_with_no_model_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `agent_model_guard.py` passes `subagent_type: fork` right after the invalid-name check. A fork has no agent file and
  ignores a call-site model, so the opus, inherit and pin checks cannot apply to it.
- A fixture copies a real fork launch's `tool_input` (prompt redacted).

## Evidence

- Queue item `agent-model-pin-hook-blocks-every-fork-dispatch`: the hook denied every fork with "has no model pin",
  because no `fork.md` agent file exists. Passing a model does not help: the harness ignores it for a fork.
- Both new tests fail on the base commit and pass after.

## Result

- `test_agent_model_guard` passes (26 tests); ruff passes.

## Watch

—

## Back-out

Revert the commit.
