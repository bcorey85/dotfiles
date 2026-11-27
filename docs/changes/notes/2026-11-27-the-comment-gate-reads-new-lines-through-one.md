---
type: "Change"
change_type: "changed"
title: "The comment gate reads new lines through one helper"
description: "comment-bloat-gate's counting_texts now calls stripped_added for the lines HEAD lacks, so the added set and the counting set come from one function; no behavior change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T12:31:19-06:00"}
seq: 4
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_a_block_built_two_lines_per_edit_blocks_on_the_second_edit"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`counting_texts` in `comment_bloat_gate.py` returns `stripped_added(file_lines, committed)` in place of its own copy of the same set math.

## Evidence

census: the branch-final smell review found the copy.

## Result

—

## Watch

—

## Back-out

Restore the two set lines in `counting_texts`.
