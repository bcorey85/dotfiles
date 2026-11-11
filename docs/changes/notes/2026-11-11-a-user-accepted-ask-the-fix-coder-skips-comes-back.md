---
type: "Change"
change_type: "fixed"
title: "A user-accepted ask the fix coder skips comes back as an ask"
description: "asks-done --by user launches the fix run with --user-ruled, and that run's packet turns each fix-first skip into an ask carrying the coder's reason, so a change the user accepted is applied or put back to the user, never dropped into skipped."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T00:30:00-06:00"}
seq: 1
kind: "fix"
components: ["skill/review", "skill/fix"]
evidence: ["session report: fix-resume-drops-a-user-accepted-ask-when"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_user_ruled_launch_turns_a_skipped_entry_into_an_ask_with_the_coders_reason"
asked: ""
proof: []
unmeasured: "No skill text changed."
---

## Change

- `review_launch.py`: `--user-ruled` (needs `--fix`) stores `user_ruled: true` in the launch record; `reviewer_dispatch.read_launch_record` takes `default=` so older records read as false.
- `review_fix_asks.py`: `asks-done --by user` puts `--user-ruled` on the launch line; `--by session` does not; `--correct --by user` makes the run user-ruled.
- `review_loop_script.fix_first`: its skips carry `given: true`.
- New `review/review_user_ruled.py`: for a user-ruled launch, `review_fix.py packet` turns each `given` skip into an ask ("You accepted this change; the fix coder skipped it: <reason>. Apply it anyway?", change = the finding) and drops it from `skipped_fp`. Review-round, repair and held-file skips stay skips.

## Evidence

The user accepted an ask through `/fix resume accept`; the fix run's coder objected, the finding landed in `skipped_fp`, and the run went on without telling the user.

## Result

The user-ruled packet tests fail before the change and pass after. `bash tests/run.sh`: 3422 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
