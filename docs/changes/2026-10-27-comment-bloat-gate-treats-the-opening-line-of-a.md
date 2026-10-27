---
type: "Change"
title: "comment-bloat gate treats the opening line of a multi-line data string as data from the opening quote"
description: "The gate searched the whole opening line of an assigned or passed multi-line string; it now searches only the text before the opening quote."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-27T15:35:11-05:00"}
seq: 115
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_marker_on_the_opening_line_of_a_multi_line_data_string_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `source_text.string_data_regions` returns a third result, `openings`, from the same single scan as the other two: for
  each line that opens a multi-line data string (a triple-quoted string assigned or passed on the line, or a backtick
  template literal), the text before the opening quote.
- `comment_bloat_gate.py` searches only that head on such a line, so `PLAN = """## Phase 1` followed by more lines is
  allowed. A docstring that opens on the same line as a marker is not a data string and still blocks, as does a marker
  in code or a comment before the opening quote.
- On a slash line that closes one template and opens another, the closing tail now stops at the new opening
  backtick.

## Evidence

- Queue item `comment-bloat-gate-still-searches-the-opening-line`: a test fixture string whose first line holds a plan
  marker was blocked although its text is data.
- The gate test and the opening-line helper tests fail on the base commit and pass after.

## Result

- `test_source_text`, `test_comment_bloat_gate` and `test_stale_prose` pass (122 tests); ruff check passes.

## Watch

—

## Back-out

Revert the commit.
