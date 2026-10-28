---
type: "Change"
title: "Pin merge-resolution routes and fix the missing-module rule"
description: "Two tests pin merge resolutions that had none (a tool fault outranks the blocker-with-asks route; an environment gap outranks a setup fault), and the review-loop's missing-module rule now excludes declared dependencies."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T05:04:25-05:00"}
seq: 168
kind: "fix"
components: ["script/full-check", "script/code-step", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_missing_declared_module_is_reported_ahead_of_a_setup_fault_marker"
asked: ""
proof: []
unmeasured: "A test pin and a one-sentence wording fix; no intake number reads either."
---

## Change

- `tests/scripts/test_full_check.py`: a log holding both a declared missing module and a setup-fault marker returns the environment gap, not the setup fault.
- `tests/scripts/test_code_step.py`: a review packet with a tool fault, a critical blocker and a reviewer question stops as a tool fault and sets no `blockerCarried`.
- `agents/review-loop.md` (and the opencode copy): a missing module from outside the repo is a code failure only when the repo's dependency files do not declare it, matching the environment-gap line below it.

## Evidence

Review of the merge resolutions of `stop_on_review_status` and `full_check.run()`: both keep every route and the result order (passed or unverified, environment gap, setup fault, failed). The two tests pass on the merged source and fail when the order is swapped (tool fault moved after the blocker route; setup fault moved above the gap check).

## Result

No source change. The review-loop sentence no longer contradicts the environment-gap rule.

## Watch

—

## Back-out

Revert the commit.
