---
type: "Change"
change_type: "fixed"
title: "asks-done refuses a conditional proposed change and corrects a logged outcome"
description: "asks-done refuses accepted or rejected on a proposed change that hangs on the ask's answer and asks for modified:, takes --correct to change a logged outcome while the fix run is unlaunched, and every ask reads Accept = make this change, Reject = leave the code."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T21:40:00-06:00"}
seq: 1
kind: "fix"
components: ["skill/review", "skill/fix", "shared/review-fork-run", "skill/audit"]
evidence: ["session report: review-ask-with-conditional-proposed-change"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_asks_done_refuses_accepted_and_rejected_on_a_conditional_change_and_logs_nothing"
asked: ""
proof: []
unmeasured: "The review-fork-run.md Resume line is call syntax: it names the exit-2 refusal's modified: answer and the --correct flag of the asks-done call the step already makes. No rule-meter run."
---

## Change

- `review_asks.py`: `is_conditional_change` owns the pattern. A change is conditional when it starts with `If not`, `If no`, `Unless`, `Otherwise`, `If the user` or `If (not )?accepted`, or holds anywhere `if yes`, `if no,`, `if (not )?(confirmed|approved)` or `if the user (confirms|approves|accepts|agrees|says)`; a condition inside ordinary code ("Return 202 if accepted by the queue", "Show the banner if the user is an admin") is not. The accept/reject wording of every ask listing lives here too.
- `review_fix_asks.py`: asks-done exits 2 and logs nothing on `accepted`/`rejected` for a conditional change, naming `modified:`. `--correct <outcome>...` logs new rows for changed outcomes, rewrites `ask-findings.md` and reprints the launch line while `asks_launch_pending` holds; with no accepted ask left it deletes the findings file, clears the launch keys and prints done. After the launch it refuses.
- `skills/audit/review.md` counts the last `ask_outcome` row per finding; `handback.py` docstring updated.
- `_shared/review-fork-run.md` Resume: one line naming the `modified:` answer to the refusal and `--correct`.

## Evidence

An ask proposed "if not confirmed, revert X"; the user said yes, asks-done logged accepted, and the fix coder made the revert, the opposite of the answer. A second asks-done printed "already logged".

## Result

The new asks-done tests fail before the change and pass after. `bash tests/run.sh`: 3396 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
