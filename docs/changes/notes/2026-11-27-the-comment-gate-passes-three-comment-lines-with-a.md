---
type: "Change"
change_type: "changed"
title: "The comment gate passes a three-line comment block with a nudge to recheck it"
description: "comment-bloat-gate now passes a run of up to three added non-kept comment lines; a run of exactly three passes with additionalContext that asks the coder to reread the block and delete, cut or rename it unless a busy engineer new to the code needs it; a run of four or more is blocked."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T18:00:00-06:00"}
seq: 5
kind: "user-rule"
components: ["script/comment-bloat-gate", "lib/hook_input"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-27: asked by the user"
proof: []
unmeasured: "whether the nudge makes coders delete or shorten a three-line block more often than they keep it"
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`MAX_FREE_BLOCK_LINES` goes from 2 to 3. A run of exactly three added non-kept lines passes, and the gate prints PostToolUse `additionalContext` that lists the lines and asks the coder to reread them: keep the block only if a busy engineer new to the code needs it to change the code safely, else delete it, cut it, or turn it into a name. A run of four or more is blocked as before. A file outside a git work tree or ignored by git gets no nudge, as it gets no block. `lib/hook_input.py` gains `emit_added_context`.

## Evidence

user request. `tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_a_non_kept_comment_block_passes_up_to_two_lines_is_nudged_at_three_and_blocks_at_four` pins 1-2 silent, 3 nudged and 4 blocked; `test_a_three_line_block_in_an_ignored_file_gets_no_nudge` pins the scratch case.

## Result

—

## Watch

—

## Back-out

Restore `comment_bloat_gate.py`, `lib/hook_input.py` and the test file from the commit before this change.
