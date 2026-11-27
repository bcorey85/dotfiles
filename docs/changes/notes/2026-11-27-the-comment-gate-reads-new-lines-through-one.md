---
type: "Change"
change_type: "changed"
title: "The comment gate reads HEAD once and counts every comment line of a new file"
description: "comment-bloat-gate reads HEAD once per edit, counts every comment line of a file HEAD lacks so a new file cannot be built two comment lines per edit, and counting_texts reuses stripped_added."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T12:31:19-06:00"}
seq: 4
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_a_block_built_two_lines_per_edit_in_an_uncommitted_file_blocks_on_the_second_edit"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`counting_texts` in `comment_bloat_gate.py` returns `stripped_added(file_lines, committed)` in place of its own copy of the same set math. `check` reads HEAD once per edit and passes it to both readers. A file HEAD lacks counts every comment line; only a failed git read falls back to this edit's lines.

## Evidence

census: the branch-final smell review found the copy; the branch review found the new-file bypass and the second HEAD read. The test fails on the gate before this change.

## Result

—

## Watch

—

## Back-out

Restore the two set lines in `counting_texts`.
