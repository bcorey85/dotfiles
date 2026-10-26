---
type: "Change"
title: "code_step counts the hand-back cap from the agent's launch"
description: "The /code wait cap starts at the Agent call's launch, not at the printed dispatch, so a worker that holds a dispatch no longer gets a false has-not-handed-back stop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T13:09:09-05:00"}
seq: 54
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_the_review_wait_cap_counts_from_the_launch_not_from_the_printed_dispatch"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The hand-back wait cap for a dispatched coder or review-loop counts from the newest dispatch's launch event when one
  is logged, never earlier than the printed dispatch. A resumed agent still counts from its first wait.
- The cap stop reads "has not handed back in N seconds, counted from <time>" in place of "dispatched at <time>".

## Evidence

- A peer's /code run: the worker held its dispatches about 30 minutes for an orchestrator, then launched the
  review-loop and ran `resume`. Resume stopped with the review-loop past the cap, though it had just launched: the
  cap (1710 seconds) counted from the printed dispatch.
- The new test fails on the base commit and passes after.

## Result

- Full dotfiles suite (2267 tests) and ruff check pass on the worktree.

## Watch

—

## Back-out

Revert the commit.
