---
type: "Change"
change_type: "fixed"
title: "code_wait review says why when the loop process is gone, and a second detach in one repo stops"
description: "A second /code run in the same repo can no longer overwrite the running review loop's pid and output, and the review wait now names the open requests and the restart step, exiting 1, when the loop process is gone or left no output."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T23:55:15-06:00"}
seq: 15
kind: "fix"
components: ["script/code-wait", "script/code-review-start", "skill/code"]
evidence: ["defect report", "transcripts", "tests"]
watches: []
test: "tests/scripts/test_code_wait.py::ReviewerRequestTest::test_a_loop_process_gone_with_a_named_reviewer_at_work_says_why_and_exits_one"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_review_start.detach` stops with the running pid and loop folder when the pid in `<git dir>/code-phase/pid` is
alive, before it truncates `review.out` or writes a pid. `code_wait.wait_review` exits 1 with `LOOP_GONE`, the open
request lines, the loop folder and the restart step when the loop process is not running and a request has no
report. It also exits 1, naming `review.out`, when the ended loop left no output. The /code skill and the shared
review-fork run say "On exit 1, do the step its last line names".

## Evidence

On 2026-11-08 two /code forks from two sessions ran in `~/agent-evals` and shared `<git dir>/code-phase`. Fork B's
detach at 01:41:26 truncated `review.out` and wrote its loop pid (3116963). Fork A read that pid file at 01:41:26
and ran `kill 3116963` at 01:41:31, stopping B's loop process. B's `code_wait.py review` with four reviewer pairs
then found the pid dead (code_wait.py `review_running`), skipped the unwritten reports, and printed the empty
`review.out` (old line 256), exit 0. Three calls returned an empty line. The tests fail before the fix and pass
after; `test_code_review_start.py::CodeReviewStartTest::test_detach_refuses_while_another_review_loop_of_this_repo_runs`
covers the detach stop.

## Result

`bash tests/run.sh` passes.

## Watch

None: the intake does not count empty `code_wait.py review` results.

## Back-out

Drop the `review_running` check from `detach` in `scripts/code/code_review_start.py`, the `LOOP_GONE` and empty-output
branches and the `restart` field from `scripts/code/code_wait.py`, and the skill line changes, with the tests.
