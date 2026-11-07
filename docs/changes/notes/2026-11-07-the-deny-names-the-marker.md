---
type: "Change"
change_type: "fixed"
title: "Comment-bloat deny names the marker"
description: "The comment-bloat-gate marker deny prints the text each line matched, so a coder knows what to drop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T01:28:20-06:00"}
seq: 1
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_the_deny_names_the_bare_marker_text"
asked: ""
proof: []
unmeasured: ""
---

## Change

`marker_hit` returns the matched text; each deny line ends `<- marker "<text>"`. A lookbehind keeps `AC1` and `(AC2)` from printing with a leading `:` or `(`.

## Evidence

judgment: a coder retried the same docstring Edit three times because the deny named the line, not the marker. The new test fails on the base commit and passes after.

## Result

Median run time over 21 runs: comment_bloat_gate 34 ms against a bare Python start of 8 ms.

## Watch

—

## Back-out

Revert the commit's hunks in the named files.

