---
type: "Change"
title: "Scripted review loop records its clean tree for the commit gate"
description: "When the scripted review loop hands back converged or deferred, it records the tree it ended on as reviewed, so the session's commit of that tree passes the commit gate even when the /code run that launched it ended first."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T12:46:57-05:00"}
seq: 90
kind: "fix"
components: ["agent/review-loop", "script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_converged_loop_lets_the_commit_through_when_its_code_run_ended_first"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_script.py` records the working tree as reviewed for its `--session` after it writes the hand-back and
  stop rows, under the same rule as `review-gate-mark clean`: only when `handback.false_clean_reason` returns none.
- The session is the one /code pinned, which is the session that commits.

## Evidence

- One work sighting: a /code run ended while its review loop still ran, so no phase finish and no clean mark ran.
  The commit gate then demanded a fresh full /review of a tree that had already converged and passed the full suite.
  The re-review cost about an hour.
- Before the fix the loop script wrote its converged hand-back but no reviewed tree; only the /code phase finish and
  `review-gate-mark clean` recorded one.
- The new test fails on the base commit (the gate denies) and passes after. A second test checks that a loop that ends
  in a critical blocker leaves the gate closed.

## Result

- Full suite: see the install commit.

## Watch

— (a fix; its test is the check)

## Back-out

Revert the commit. The reviewed-tree file is the one the gate already reads.
