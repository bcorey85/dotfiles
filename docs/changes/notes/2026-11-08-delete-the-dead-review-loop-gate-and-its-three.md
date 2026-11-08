---
type: "Change"
change_type: "removed"
title: "delete the dead review-loop gate and its three hook registrations"
description: "review_loop_gate.py and its PreToolUse Agent, PreToolUse Bash and SubagentStop registrations are gone; every branch keyed on the deleted review-loop agent."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T10:05:00-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop-gate", "script/review-loop-packet"]
evidence: ["run-review-and-fix-on-review-loop-script"]
watches: []
test: "tests/scripts/test_hook_module_imports.py::test_settings_register_no_gate_for_the_deleted_review_loop_agent_and_no_missing_script"
asked: ""
proof: []
unmeasured: ""
---

## Change

Deleted `claude/.claude/scripts/review/review_loop_gate.py`, its three `settings.json` registrations, its test file, two `test_review_fix_script.py` tests that ran it, their now-unused fixture, and its entries in `tests/lint.sh`, `test_toolkit_self_location.py`, `test_hook_if_filters.py` and `test_hook_module_imports.py`. A new test fails when settings registers the gate or any script that does not exist.

## Evidence

run-review-and-fix-on-review-loop-script. Every branch of the gate keyed on `agent_type` or `subagent_type` `review-loop`, an agent deleted in c16bd3b2. The scripted loop's `review_loop_packet.py` imported its `record_stop` to write the hand-back stop row; it now writes that row through `handback_store.record` itself.

## Result

Each Agent dispatch runs one hook fewer: the gate cost 45.8 ms median through hook-python, against 8.0 ms for a bare Python start. Hooks on one matcher run in parallel, so the wall-clock gain is below the CPU saved.

## Watch

—

## Back-out

Revert the commit; the settings registrations come back with it.
