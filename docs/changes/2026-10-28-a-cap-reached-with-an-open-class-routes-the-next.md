---
type: "Change"
title: "A cap-reached with an open class routes the next run to the last fix diff"
description: "When a capped review run's class-closure receipt says a class is still open, review_fix.py prints a scoped review of the last fix's files as the next run and no longer offers a full rerun."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T20:16:54-05:00"}
seq: 213
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_cap_reached_with_an_open_class_routes_the_next_run_to_the_last_fix_diff_only"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_fix.py packet`: a `cap-reached` packet whose `class_closure` says a class is still open ("still open",
  "not closed", "open members" and the like) and that names `files_touched` stops with a new instruction. It reports
  the findings and prints the next dispatch: `mode: review-first`, the caller, `iter=0`, and a handoff block whose
  files are the last fix's files, with the open class under `flagged` and each remaining finding under
  `prior-issues`. It no longer says "Do not re-dispatch", and it says not to offer a full rerun.
- Any other `cap-reached` keeps the plain stop.
- Script half only. The review-loop agent prompt is unchanged: enumerating the whole class before the cap needs a
  bench.

## Evidence

- On one branch that added a log-comparison heuristic, six review-loop runs in a row ended cap-reached, each
  finding one more log shape. Each took 20-30 minutes. Only a run scoped to the last edit converged.
- The receipt is free text, so the open-class test matches its words. A receipt that does not use them falls back
  to the plain stop, which is the old behavior.

## Result

- The new test fails before (plain stop, no scoped dispatch) and passes after. A second test keeps the plain stop
  when every class is closed.

## Watch

—

## Back-out

Revert the commit.
