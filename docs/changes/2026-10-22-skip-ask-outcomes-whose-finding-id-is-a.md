---
type: "Change"
title: "Skip ask outcomes whose finding id is a placeholder"
description: "review-fix.py asks-done now logs an ask outcome only when its finding_id has the minted shape. A placeholder such as \"none logged\" is skipped and named, and the command no longer fails."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T07:25:39-05:00"}
seq: 1
components: ["script/review-fix", "script/handback"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/handback.py`: new `ask_finding_id(item)`. It returns the stripped id only when it matches the 16 lowercase hex chars that log-review-finding mints. Any other value returns None.
- `scripts/review-fix.py`, `asks-done`: an ask whose id fails that check is not logged. It counts in the existing "ask(s) without a finding_id" note, and stderr names the ignored value, or "(no finding_id)" when the key is missing.
- Tests: `test_handback.py`, `test_review_fix_script.py` and `test_code_step_asks.py` under `tests/scripts/`. The review-fix cases in `test_code_step_asks.py` now use 16-hex ids.

## Evidence

- Work incident: a review-loop packet carried `finding_id: none logged`. The logger refused the value because it holds a space, so 0 of 1 ask outcome rows were logged and the stage stayed at asks. A value with no space, such as `none` or `-`, was logged as a stray row that replaced no ask row.

## Result

A placeholder id no longer fails the command or writes a stray row. code-step.py has its own copy of the old check, and the next code-step change switches it to `ask_finding_id`.

## Watch

None. The intake has no count of refused or stray ask outcome rows.

## Back-out

Restore the `if not findingId` check in `log_ask_outcome`, and drop `ask_finding_id` from handback.py.
