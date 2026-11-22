---
type: "Change"
change_type: "fixed"
title: "A fix pass that deletes a comment no finding names files an ask"
description: "After each fix pass the loop puts back a removed comment line that no finding names and files an ask carrying the removal."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 31
kind: "fix"
components: ["script/review-loop-comment-removal", "script/review-loop-script"]
evidence: ["review-fix-coder-deletes-comments-without"]
watches: []
test: "tests/scripts/test_review_loop_script.py::CommentRemovalLoopTest::test_a_pass_that_deletes_an_unnamed_comment_gets_the_line_back_and_an_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

New mixin `review/review_loop_comment_removal.py` reads removed comment lines of the pass diff, puts back the unnamed ones through `lib/protected_lines.py`, and files one ask. A comment a finding names stays deleted.

## Evidence

A /review fix pass deleted a code comment and listed it as a fix. The repo rule says comments go only with the user's permission.

## Result

CommentRemovalLoopTest and CommentRemovalUnitTest in `test_review_loop_script.py`.

## Watch

None.

## Back-out

Revert the commit.
