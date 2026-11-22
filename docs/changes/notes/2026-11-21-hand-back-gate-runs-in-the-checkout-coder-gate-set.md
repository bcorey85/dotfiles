---
type: "Change"
change_type: "fixed"
title: "Hand-back gate runs in the checkout coder_gate set ran in"
description: "coder_gate.py set writes a session pointer to its gate file, and the hand-back hook uses that gate, not the gate of the hook's cwd, so a failure in another checkout never blocks the run."
generated: {"by": "claude-opus-5-5/lane-code-gates", "at": "2026-11-21T18:44:44-06:00"}
seq: 3
kind: "fix"
components: ["script/coder-gate", "script/script-utils"]
evidence: ["queue item code-hand-back-gate-runs-in-the-session-s-worktree: the hook read the gate of the session's cwd checkout, not the run's"]
watches: []
test: "tests/scripts/test_coder_gate.py::SessionPointerTests::test_a_hook_from_another_checkout_runs_the_gate_set_in_the_first_checkout"
asked: ""
proof: []
unmeasured: ""
---

## Change

`coder_gate.py set` writes a per-session pointer (keyed by `CLAUDE_CODE_SESSION_ID`) to the absolute gate file. `run_hook` reads the event's `session_id`. When a pointer exists it uses that gate file; if that file is gone it allows and runs no gate. With no pointer, or an unreadable one (reported on stderr), it uses the cwd as before. `clear` removes the pointer when it names this gate file.

## Evidence

`test_a_hook_from_another_checkout_runs_the_gate_set_in_the_first_checkout` and `test_a_pointer_whose_gate_file_is_gone_allows_and_does_not_run_the_cwds_gate` fail without the change.

## Result

The phase gate and the full suite pass, apart from `test_rule_anchors`, which also fails on master.

## Watch

One pointer per session, the last `set` wins: a stale pointer (a run that died before `clear`, or a second concurrent run in the same session) gates every later coder hand-back of that session with that gate until `clear` or `MAX_GATE_AGE_SECONDS`. One /code run per session is the supported model.

A hand-back allowed because the pointer named a gate file that was gone while a real gate existed in the cwd.

## Back-out

Remove the pointer write from `set_gate`, the pointer read from `run_hook`, and the removal from `clear_gate`.
