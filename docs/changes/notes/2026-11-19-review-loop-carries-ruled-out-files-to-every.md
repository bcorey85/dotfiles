---
type: "Change"
change_type: "fixed"
title: "review loop carries ruled-out files to every dispatch and guards them"
description: "review_launch takes a user's ruled-out file list, every coder and reviewer prompt of the loop lists it, a pass that edits or deletes a ruled-out file has it put back, and a diff file is deleted only under a finding that names the deletion."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:11-06:00"}
seq: 3
kind: "fix"
components: ["script/review-loop-script", "script/review-fix", "skill/review"]
evidence: ["review-loop-ignores-user-ruled-scope-and-re"]
watches: []
test: "tests/scripts/test_review_loop_coder.py::RuledOutLoopTest::test_a_ruled_out_file_a_coder_edits_or_creates_is_put_back_and_noted"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_launch.py` writes a ruled-out line into the prompt header and the relaunch args. `review_loop_prompts.py`
adds the rule to each reviewer and coder prompt. The new `review/review_loop_ruled_out.py` `PassGuard` backs up the
ruled-out files and the diff files before each pass, puts back an edited, created or deleted ruled-out file, and
restores a deleted diff file unless a finding names its deletion, move or rename. A finding on a ruled-out file goes
to skipped_fp. A directory a pass makes at a ruled-out path is left and noted.

## Evidence

The loop edited files the user had ruled out of scope and deleted a file in the diff with no finding naming it.

## Result

`RuledOutLoopTest` in `test_review_loop_coder.py`, plus `test_review_launch.py` and `test_review_loop_prompt_file.py`.

## Watch

None.

## Back-out

Revert the commit.
