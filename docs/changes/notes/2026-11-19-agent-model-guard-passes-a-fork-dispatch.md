---
type: "Change"
change_type: "fixed"
title: "agent-model-guard passes a fork dispatch"
description: "agent-model-guard lets an Agent call with subagent_type fork through with no model pin, and still denies an unpinned or opus non-fork dispatch."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T12:55:21-06:00"}
seq: 6
kind: "fix"
components: ["script/agent-model-guard"]
evidence: ["agent-hooks-fork-dispatch-blocked-by-both-model"]
watches: []
test: "tests/scripts/test_agent_model_guard.py::AgentModelGuardTest::test_fork_without_model_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

`agent-model-guard.sh` exits 0 for `subagent_type: "fork"` right after it reads the type. A fork runs on the parent model, so no pin applies.

## Evidence

A fork dispatch with no model was denied with "no model pin", since no agent file exists for `fork`.

## Result

`AgentModelGuardTest` in `test_agent_model_guard.py`: a fork passes; an unpinned or opus non-fork agent is denied.

## Watch

None. The CB Security Hooks package needs the same fork pass, or a regenerate drops it.

## Back-out

Revert the commit.
