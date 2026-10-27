---
type: "Change"
title: "Phase commit uses the plan's named commit line, never a none summary"
description: "code_step's phase commit takes its subject from the phase's Commit `...` line in the plan when there is one; otherwise from the coder's Implemented summary, unless that summary starts with none, when it takes the phase title."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:00:04-05:00"}
seq: 73
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_commit_subject.py::CommitSubject::test_the_plan_named_commit_line_beats_the_coder_summary"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_boundary.planned_commit_subject` reads the current phase's own section of the plan and returns the
  subject of its first `Commit `...`` line, or "" when the section names none.
- `commit_message(repo_dir, state)` uses that subject first. With no plan line it uses the coder's first Implemented
  summary, unless the summary starts with the word `none`; then it uses the phase title. The ticket prefix rule is
  unchanged.
- `phase_commit`, the only caller, passes `repo_dir`.

## Evidence

- A test-only phase named its commit in the plan. The coder's hand-back said `Implemented: none (test-only change;
  ...)`, and code_step committed with the subject `<TICKET>: none (test-only change; ...)`. The review-commit gate
  then blocked the message-only amend, so the wrong subject stayed on the branch.
- The new tests fail on the base commit and pass after.

## Result

- Full suite (2385 tests) and ruff pass on the live checkout.

## Watch

—

## Back-out

Revert the commit.
