---
type: "Change"
change_type: "fixed"
title: "A no-code ruling that asks for a test edit is a change"
description: "is_no_code_ruling reads a note as a change when a clause after the no-code words asks for a test edit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 28
kind: "fix"
components: ["script/ruled-change-text"]
evidence: ["review-resume-skips-test-only-edit-ruled-as-no"]
watches: []
test: "tests/scripts/test_ruled_change_text.py::RuledNoteTest::test_a_no_code_note_that_asks_for_a_test_edit_is_a_change"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/ruled_change_text.is_no_code_ruling` is false when a clause starts with an edit verb and names a test word, after optional lead-ins. A negated verb is not an edit.

## Evidence

A resume ruling "no code change; add a case to the test loop and pin the output" was read as no code, and the fixer skipped the test edit.

## Result

RuledNoteTest in `test_ruled_change_text.py`.

## Watch

None.

## Back-out

Revert the commit.
