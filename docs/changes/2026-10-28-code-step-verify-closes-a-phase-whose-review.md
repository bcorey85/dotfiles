---
type: "Change"
change_type: "fixed"
title: "code-step: verify closes a phase whose review converged"
description: "verify now also runs whenever the phase's review converged and no coder works on it, so the runner records the checks. Before, it ran only after a failed Automated Verification or a plan-format stop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:51:07-05:00"}
seq: 184
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_verify_closes_a_reviewed_phase_stopped_for_another_reason"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `verify` runs when the saved review status is converged or deferred and the stage is not a coder, plan-coder, skill
  or done stage. It still runs at a verification or plan-format stop as before.
- The guard lives in one function, `guarded_verb_runs`, which `code_step.py` and `start` both read.

## Evidence

- A session whose checks passed could not reach `verify` through the runner. It ran the checks itself, outside the
  runner's record.

## Result

- The runner runs and records the checks once the phase's code is reviewed.

## Watch

—

## Back-out

Revert the commit.
