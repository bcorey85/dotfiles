---
type: "Change"
change_type: "fixed"
title: "The session-start notice skips a loop of another branch or a detached loop"
description: "The session-start notice prints no dispatch action for a loop of another branch or a loop detached for a code fork, and names every loop's age and branch."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 30
kind: "fix"
components: ["script/reviewer-dispatch", "script/waiting-review-launch", "script/review-launch"]
evidence: ["session-start-hook-resurfaces-stale-review-loop"]
watches: []
test: "tests/scripts/test_waiting_review_launch.py::WaitingReviewLaunchTest::test_a_loop_of_another_branch_prints_no_action_but_names_its_age_and_branch"
asked: ""
proof: []
unmeasured: ""
---

## Change

`launch.json` saves the branch, launch time and detach flag. `reviewer_dispatch.waiting_launch_lines` leaves out a loop of another branch or a detached one, on one line with its age and branch. The header names age and branch, not "this session".

## Evidence

On a compacted resume, the hook printed a dispatch action for a 7-day-old loop of another branch and said it was launched in this session.

## Result

WaitingReviewLaunchTest in `test_waiting_review_launch.py` and the waiting-launch tests in `test_reviewer_dispatch.py`.

## Watch

None.

## Back-out

Revert the commit.
