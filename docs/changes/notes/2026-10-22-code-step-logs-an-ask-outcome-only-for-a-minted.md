---
type: "Change"
change_type: "fixed"
title: "code-step logs an ask outcome only for a minted finding id"
description: "code-step's ask-outcome logger now uses handback.ask_finding_id, as review-fix does. It skips and names a placeholder id, and it names a logger failure on stderr."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T09:51:55-05:00"}
seq: 10
kind: "fix"
components: ["script/code-step"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/code-step.py`, `log_ask_outcomes`:
  - It loads `handback` and keeps an ask only when `ask_finding_id` returns an id. If `handback` does not load, it logs nothing and says why.
  - A skipped ask is named on stderr, with "no finding_id" or the ignored value.
  - It reads the return code of `log-review-finding`, and on a failure it names the id, the exit code and the output.
- Tests: `tests/scripts/test_code_step_asks.py` uses 16-hex ids and asserts the logger call count.

## Evidence

- Work incident: a review-loop packet carried `finding_id: none logged`. review-fix got the fix first. code-step had its own copy of the old empty-id check, so two asks with `finding_id: none` wrote two stray rows, and a refused value failed with no message.

## Result

Both ask-outcome loggers apply one id check. A logger failure is visible.

## Watch

None. The intake has no count of refused or stray ask outcome rows.

## Back-out

Restore the `if not findingId` check and the unchecked `run_command` call in `log_ask_outcomes`.
