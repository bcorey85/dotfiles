---
type: "Change"
change_type: "fixed"
title: "Review prompt drops later-phase files this phase already changed"
description: "code_review_start.py no longer lists a later-phase file that the current phase changed, so reviewers stop skipping the lines the phase wrote in it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T01:35:49-06:00"}
seq: 3
kind: "fix"
components: ["script/code-review-start"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_review_start.py::CodeReviewStartTest::test_a_later_phase_file_this_phase_already_changed_is_not_a_later_phase_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

New `phase_changed_files(repo, base)` reads `script_utils.changed_files` against the phase base (`[]` when the base is no commit). `review_prompt` takes `phase_changed` and leaves those paths out of `later-phase files:`.

## Evidence

judgment: a review marked lines this phase wrote in a file a later phase also names as out of scope, and never reviewed them. The new test fails on the base commit and passes after.

## Result

`test_code_review_start.py` 17 of 17 pass; lint clean.

## Watch

—

## Back-out

Remove `phase_changed_files`, the `phase_changed` parameter and its filter, and the new test.
