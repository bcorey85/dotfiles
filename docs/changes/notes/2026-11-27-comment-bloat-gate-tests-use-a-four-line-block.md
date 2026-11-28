---
type: "Change"
change_type: "fixed"
title: "comment-bloat gate tests use a four-line block over the three-line cap"
description: "The ideographic-space and invalid-UTF-8 comment-bloat tests now add a four-line comment block, so they test their own case against a block the three-line cap still refuses."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T20:03:11-06:00"}
seq: 6
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_review_fixes.py::IdeographicSpaceTest::test_comment_bloat_gate_reads_an_ideographic_space_as_indent; tests/scripts/test_review_fixes.py::InvalidUtf8StdinTest::test_comment_bloat_gate_blocks_an_added_comment_next_to_invalid_utf8"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The two tests in `tests/scripts/test_review_fixes.py` build their added comment run from `BLOCKED_RUN_LENGTH`, which is the gate's `MAX_FREE_BLOCK_LINES` plus one, so it is four lines today in place of the fixed three. Their assertions are unchanged: exit 2 and the `2: # note 1` line on stderr. The gate is unchanged.

## Evidence

Commit 905a88fe1 raised `MAX_FREE_BLOCK_LINES` from 2 to 3, so a three-line run passes with a nudge. Both fixtures added exactly three lines, and on master fb9eeb414 both tests got exit 0 where they expect 2. With four lines, `python3 tests/parallel_tests.py test_review_fixes.py` gives 14 tests, 0 failed.

## Result

Both tests pass again, and `test_review_fixes.py` is green.

## Watch

None: the tests are the check.

## Back-out

`git revert` the commit.
