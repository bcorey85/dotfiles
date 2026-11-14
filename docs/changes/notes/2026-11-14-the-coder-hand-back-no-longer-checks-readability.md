---
type: "Change"
change_type: "removed"
title: "The coder hand-back no longer checks readability"
description: "The readability check is gone from every gate command list: the coder's hand-back is never refused for a readability hit, and the review loop runs no readability pass. readability_check.py and readability_ts.mjs are deleted; the stale-prose check stays."
generated: {"by": "human:brandon", "at": "2026-11-14T11:01:06-06:00"}
seq: 1
kind: "user-rule"
components: ["script/coder-gate", "script/review-loop-script", "script/gate-commands", "script/code-review-start"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-14: just remove that gate. its not worth it"
proof: []
unmeasured: "The change removes a check; no run measures its effect."
---

## Change

`gate_commands.main` and `code_review_start.phase_gate_commands` no longer append the readability command, `review_loop_script.scoped_tests_pass` runs only the stale-prose hit check, and `review_loop_scoped_tests.test_commands_of` leaves out only the stale-prose check. `coder_gate` loses `READABILITY_SCRIPT`, `is_readability_check`, `readability_command` and the `readability_failed` field of its log rows. `readability_check.py`, `readability_ts.mjs` and their tests are deleted. The coder-core readability style rules stay as prompt text.

## Evidence

User rule, 2026-11-14: "just remove that gate. its not worth it".

## Result

`bash tests/run.sh` passes.

## Watch

None. The `coder-readability-handback-denials` watch has no new rows to read once the gate log stops carrying `readability_failed`.

## Back-out

Restore the deleted scripts and the removed `coder_gate` functions, and append `coder_gate.readability_command` again in `gate_commands.main` and `code_review_start.phase_gate_commands`, with the readability hit check in `review_loop_script.scoped_tests_pass`.
