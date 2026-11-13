---
type: "Change"
change_type: "fixed"
title: "a loop coder may delete an untracked file an earlier coder of the same loop wrote"
description: "The review loop no longer restores an untracked file that an earlier coder call of the same loop created, so a later coder can remove a stale duplicate."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-13T09:00:00-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_coder.py::UntrackedDeletionTest::test_a_file_an_earlier_call_made_stays_deleted_with_no_fault_note"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_loop_coder.py`: `coder_call` records, per call, the untracked files present after it that were absent
before it (`LOOP_WRITTEN`, kept for the whole loop run). A later call does not back up or restore a recorded file, and
a recorded file that is gone leaves the record. Every other untracked file is still backed up and restored with the
tool-fault note, except that a file anyone else writes while a coder call runs counts as that call's file.

## Evidence

judgment: a coder left a stale duplicate file, a later coder deleted it, the loop restored it, the type check stayed
red and the loop ended deferred.

## Result

The new test fails on the old tree (the file comes back, with a fault note) and passes.

## Watch

None: a fixed rule.

## Back-out

Revert the commit.
