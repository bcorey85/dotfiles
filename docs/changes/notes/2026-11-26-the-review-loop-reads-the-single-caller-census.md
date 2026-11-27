---
type: "Change"
change_type: "fixed"
title: "The review loop reads the single-caller census against its review base"
description: "A based review's smell-reviewer prompt now lists census entries for the whole branch, such as a superseded helper an earlier branch commit added; phase_change_file.py exits 2 with a reason when the change-file check cannot run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T02:01:04-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop-script", "script/phase-change-file"]
evidence: ["tests/scripts/test_review_loop_census.py", "tests/scripts/test_phase_change_file.py"]
watches: []
test: "tests/scripts/test_review_loop_census.py::ReviewLoopCensusTests.test_a_based_review_lists_the_helper_a_commit_before_head_added"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`LoopRun.review_request` passes `self.review_base` to `reviewer_prompt` as the census base, so the single-caller census reads the same range as the nearest-functions block. Before, it always read against HEAD.

`phase_change_file.py` catches `OSError` when it starts `.githooks/change-file-check` (for example, a check that lost its exec bit) and exits 2 with `cannot run`. Before, it crashed with a traceback and exit 1, which /code reads as "write a change file".

## Evidence

`test_review_loop_census.py` builds a repo whose branch commit adds `old_helper` and whose work tree supersedes it. The based review missed `old_helper` before the change and lists it after. `test_phase_change_file.py` gains a test with a non-executable check: before, a traceback and exit 1; after, exit 2.

## Result

A based review's smell-reviewer sees census entries for the whole branch.

## Watch

—

## Back-out

Drop the `self.review_base` argument in `review_loop_script.py` `review_request`, and the `try` around the check run in `phase_change_file.py`.
