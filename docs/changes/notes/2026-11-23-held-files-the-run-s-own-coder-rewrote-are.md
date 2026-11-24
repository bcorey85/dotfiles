---
type: "Change"
change_type: "fixed"
title: "Held files the run's own coder rewrote are reviewed instead of flagged as a tool fault"
description: "A file another session left dirty at phase start, which this phase's coder then rewrote, is now released into the review and named as released; before, review skipped it and the wait printed a tool fault, so the coder's change went unreviewed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T01:21:08-06:00"}
seq: 3
kind: "fix"
components: ["script/code-review-start", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_review_start.py::CodeReviewStartTest::test_a_held_file_a_coder_of_the_run_rewrote_is_released_and_reviewed"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`code_review_start.py`: when a start record names a holder, a held dirty file whose bytes changed since the run start
is checked against the files the recorded sessions' coder subagents wrote during the run. A match is the run's own
change: it leaves the held rows and the changed list, so review reads it, and the scope gets a new `held_released`
field with a note naming it. A changed file no coder of the run wrote stays held and stays a tool fault. `held_scope`
now returns a named `HeldScope` in place of a tuple. `code_wait.py` prints a `released held files …` line on the
phase route when the scope file lists any.

## Evidence

Judgment from the code: the recorded-holder route held every dirty file for the whole phase, so a coder that edited
one put its change outside the review and the wait reported it as a fault, though the untracked-file route already
used the same coder-write attribution.

## Result

Tests: a coder-rewritten held file is released, kept out of `held_changed`, and noted; a held file only another
writer changed stays held as a fault; the wait output names a released file and prints no fault. The first fails on
the tree before the change with the file still held.

## Watch

None.

## Back-out

`git revert` the commit.
