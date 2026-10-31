---
type: "Change"
change_type: "fixed"
title: "A check stop's own CLAUDE.md fix no longer trips a plan-drift question"
description: "When the repo's CLAUDE.md has an uncommitted change after a full check stop, review-again tells the review that the edit answers the stop. The review no longer asks the plan-drift question."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T11:05:00-05:00"}
seq: 372
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_a_review_after_a_check_stop_is_told_the_claude_md_line_is_the_stops_fix_not_plan_drift"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `command_review_again` adds a `RESOLVED` block to the handoff's `plan_impact` after a `check-unverified` or `check-not-run` stop when the repo's CLAUDE.md has an uncommitted change. The block says that edit answers the stop and is not plan drift. It names the check stop rule as its source. An earlier ruling stays above it, and a second stop adds no copy.

## Evidence

- One session reported the fix line raising a plan-impact question on `review-again`. The spec named only source files, so the review stopped a second time.

## Result

- The new test fails without the block and passes with it. `test_code_step_hand_back.py` passes: 623 tests, 0 failed, 604 skipped, 19 executed.

## Watch

None: this fires on a rare stop, and no intake number counts it.

## Back-out

Revert the commit.
