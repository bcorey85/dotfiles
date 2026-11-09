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
unmeasured: "The reworded 'On exit 1' line has no rule-meter run: rule_meter.py cuts a rule only from an agent file or a skill the agent's frontmatter preloads, and code-fork preloads none (the /code skill and review-fork-run.md reach it as prompt text), and no fixture stubs a detached review loop, code_wait.py's exit-1 output and the Agent dispatch it answers."
---

## Change

`code_review_start.detach` stops with the running pid and loop folder when the pid in `<git dir>/code-phase/pid` is
alive, before it truncates `review.out` or writes a pid. `code_wait.wait_review` checks the ended loop's `packet.txt`
first. In the /code phase run it prints `review.out` with exit 0 only when the loop wrote that packet; for a launched
loop it prints the packet command once `packet.txt` exists. A crash packet counts.
Only when the ended loop left no packet does it exit 1: with `LOOP_GONE`, the open request lines, the loop folder
and the restart step when a request has no report, else with the run's `no_output` message (the file it reads) and
the restart step. The /code skill and the shared review-fork run say "On exit 1, do the step its last line names"
once, covering the first wait and every later one.

## Evidence

On 2026-11-08 two /code forks from two sessions ran in `~/agent-evals` and shared `<git dir>/code-phase`. Fork B's
detach at 01:41:26 truncated `review.out` and wrote its loop pid (3116963). Fork A read that pid file at 01:41:26
and ran `kill 3116963` at 01:41:31, stopping B's loop process. B's `code_wait.py review` with four reviewer pairs
then found the pid dead (code_wait.py `review_running`), skipped the unwritten reports, and printed the empty
`review.out` (old line 256), exit 0. Three calls returned an empty line. The tests fail before the fix and pass
after; `test_code_review_start.py::CodeReviewStartTest::test_detach_refuses_while_another_review_loop_of_this_repo_runs`
covers the detach stop.

## Result

`bash tests/run.sh` passes. The skill line is unmeasured (see `unmeasured`).

## Watch

None: the intake does not count empty `code_wait.py review` results.

## Back-out

Drop the `running_review_pid` check from `detach` in `scripts/code/code_review_start.py`, the `print_ended_loop`
function (`LOOP_GONE` and empty-output branches) and the `no_output` and `restart` fields of `ReviewRun` in
`scripts/code/code_wait.py`, and the skill line changes, with the tests.
