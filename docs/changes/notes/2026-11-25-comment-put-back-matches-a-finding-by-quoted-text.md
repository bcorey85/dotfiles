---
type: "Change"
change_type: "fixed"
title: "Comment put-back matches a finding by quoted text"
description: "A comment a fix pass removes stays removed when a finding of the same file quotes its whole text, even after its line moved, instead of being put back and held as an ask."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T16:20:05-06:00"}
seq: 4
kind: "fix"
components: ["script/review-loop-comment-removal", "script/source-text"]
evidence: ["tests/scripts/test_review_loop_script.py", "tests/scripts/test_source_text.py"]
watches: []
test: "tests/scripts/test_review_loop_script.py::CommentRemovalUnitTest::test_a_finding_that_quotes_a_comment_whose_line_moved_keeps_it_removed_with_no_ask"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

review_loop_comment_removal.py counts a removed comment as named when a finding of the same file holds a quoted span whose whole text equals the comment's body. Line and span matching stay. source_text.py gains `comment_body`, which strips the `#`, `//` and block-comment markers and collapses whitespace.

## Evidence

`CommentRemovalUnitTest.test_a_finding_that_quotes_a_comment_whose_line_moved_keeps_it_removed_with_no_ask` fails before the change: the comment was put back and an ask filed, because the finding's line no longer matched. Twelve more cases pin the edges: a quote of a longer comment, a bare word, a quote in another file's finding, and a finding that quotes nothing all still put the comment back and ask.

## Result

An audit-driven comment cleanup is no longer undone after earlier edits move the lines.

## Watch

None.

## Back-out

Revert the commit.
