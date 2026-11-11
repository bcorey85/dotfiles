---
type: "Change"
change_type: "fixed"
title: "A user-accepted ask the fix coder skips comes back as an ask"
description: "asks-done --by user puts one --user-ruled N per user-ruled finding on the fix run's launch line, and that run's packet turns each fix-first skip of such a finding into an ask carrying the coder's reason, so a change the user accepted is applied or put back to the user, never dropped into skipped."
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

- `review_launch.py`: `--user-ruled` (needs `--fix`) stores `user_ruled` in the launch record as the list of the accepted findings' texts; `reviewer_dispatch.read_launch_record` takes `default=` so a record with no key reads as none.
- `review_fix_asks.py`: `asks-done --by user` puts one `--user-ruled N` on the launch line for each finding the user ruled on; `--by session` does not; `--correct --by user` marks only the findings it re-answers.
- `review_loop_script.fix_first`: its skips carry `given: true`.
- New `review/review_user_ruled.py`: `review_fix.py packet` turns each `given` skip of a finding named in `user_ruled` into an ask ("You accepted this change; the fix coder skipped it: <reason>. Apply it anyway?", change = the finding) and drops it from `skipped_fp`. Review-round, repair and held-file skips stay skips. Each converted ask carries `user_ruled: true`, and `asks-done` does not refuse it as a conditional change: its change is the accepted finding's own line, so an "if the user" in it is no branch to pick.

## Evidence

The user accepted an ask through `/fix resume accept`; the fix run's coder objected, the finding landed in `skipped_fp`, and the run went on without telling the user.

## Result

The user-ruled packet tests fail before the change and pass after. `bash tests/run.sh`: 3422 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
