---
type: "Change"
change_type: "fixed"
title: "A fix coder that dies mid-edit leaves a record and its findings stay open"
description: "A fix coder that ends abnormally leaves partial-fix.json with its findings and pass diff, and the next launch re-queues those findings."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 32
kind: "fix"
components: ["script/review-loop-coder", "script/review-loop-partial-fix"]
evidence: ["review-loop-has-no-recovery-when-its-fix-coder"]
watches: []
test: "tests/scripts/test_review_loop_coder.py::DeadCoderRecordTest::test_a_coder_that_dies_after_editing_leaves_a_record_and_the_stop_note_names_the_findings"
asked: ""
proof: []
unmeasured: ""
---

## Change

On a non-zero exit, a timeout, an `is_error` reply or no final report, the loop writes `partial-fix.json` in `<git dir>/review-fix/` and the stop note names each finding as unverified. The next launch re-queues them and removes the record after the pass. A reviewer or disposition call whose reply has `is_error` set now stops the run as a crash, with no retry. A record written while git failed holds a null branch, and the next launch skips the branch check; the module docstrings of the new review modules name the fact each owns.

## Evidence

A fix coder stopped on a spend limit partway through. The tree held a partial edit and nothing said which findings landed.

## Result

DeadCoderRecordTest in `test_review_loop_coder.py`.

## Watch

None.

## Back-out

Revert the commit.
