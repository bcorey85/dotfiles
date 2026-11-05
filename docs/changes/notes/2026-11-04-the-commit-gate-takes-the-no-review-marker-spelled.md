---
type: "Change"
change_type: "fixed"
title: "The commit gate takes the no-review marker spelled with a space"
description: "review_commit_gate.py accepts a user prompt that starts with `[no review]` as well as `[no-review]`, so a user order to commit without review is not blocked by its spelling."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T23:55:57-06:00"}
seq: 7
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_the_marker_spelled_with_a_space_orders_the_commit_too"
asked: ""
proof: []
unmeasured: ""
---

## Change

`NO_REVIEW_MARKER` becomes the tuple `NO_REVIEW_MARKERS = ("[no-review]", "[no review]")`, and `user_ordered_no_review` checks `startswith` against the tuple. The docstring names both spellings. No line is added to the hook, and its run time does not change.

## Evidence

judgment: a user typed `[no review] /commit`; the gate blocked and told the session not to ask the user, so the user had to commit by hand. The new test fails on the base commit and passes after.

## Result

`test_review_commit_gate.py` 152 of 152 pass; lint clean.

## Watch

—

## Back-out

Restore the single `NO_REVIEW_MARKER` string and remove the test.
