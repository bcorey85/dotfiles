---
type: "Change"
change_type: "fixed"
title: "code_step commit list keeps a dirty-before file the phase edited"
description: "The phase commit command now names a file that was dirty before the phase when the phase changed its content, and the hand-back flags it as mixing earlier edits; dirty files the phase left alone stay out."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:55:06-05:00"}
seq: 81
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_the_commit_command_includes_a_file_that_was_dirty_before_the_phase_and_edited_by_it"
asked: ""
proof: []
unmeasured: "Split phase commits are not logged; no intake number reads them."
---

## Change

`phase_commit` compares the baseline content hashes it already stored: a dirty-before file whose hash changed joins the
commit list and the hand-back line "Edited by this phase, was dirty before (the commit mixes the earlier edits with this
phase's)"; a dirty-before file with an unchanged hash stays under left out.

## Evidence

A phase edited a script and its test; both were dirty before, so the printed commit named only the helper and the test
change would have shipped without the script it tests. The orchestrator caught it by reading the list.

## Result

The printed commit holds every file the phase changed.

## Watch

None.

## Back-out

Revert the commit.
