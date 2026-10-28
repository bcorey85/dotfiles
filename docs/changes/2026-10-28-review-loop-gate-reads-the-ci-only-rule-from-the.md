---
type: "Change"
title: "Review loop gate reads the CI-only rule from the reviewed repo"
description: "The review-loop stop gate looks for the Full suite: CI line in the repo the loop reviewed, not only in the hook cwd."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T01:31:43-05:00"}
seq: 164
kind: "fix"
components: ["script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::ReviewLoopGateTest::test_a_loop_reviewing_a_repo_whose_full_suite_runs_in_ci_owes_no_full_check_from_another_cwd"
asked: ""
proof: []
unmeasured: ""
---

## Change

The stop gate asked whether the hook cwd's repo leaves its full suite to CI. A loop that reviews another repo (the `repo:` line of its prompt, or the printed review-scope root) was judged by the wrong repo's CLAUDE.md. The gate now checks the reviewed repo first and falls back to the hook cwd.

## Evidence

Fail first: the new test got a block ("No full check ran") where the reviewed repo holds `Full suite: CI`; its pair test got an empty stop where the reviewed repo lacks the line but the cwd has it. Both pass after the change; all 100 gate tests pass.

## Result

A loop in a CI-only repo no longer owes a local full check when started from another directory, and a loop in a repo without the rule still owes one.

## Watch

—

## Back-out

Revert the one line in `check_stop` that passes `transcript.reviewed_root() or hook.get("cwd")`.
