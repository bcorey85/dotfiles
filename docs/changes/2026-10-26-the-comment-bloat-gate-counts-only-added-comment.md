---
type: "Change"
title: "The comment-bloat gate counts only added comment lines and skips string text"
description: "An edit that adds no net comment line passes the ratio check, the marker rule ignores text inside string literals, and the deny text keeps a comment the task requires."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:39:06-05:00"}
seq: 94
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_rewording_an_existing_comment_in_an_over_cap_file_passes; tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_marker_text_inside_a_string_literal_passes_but_a_comment_after_it_blocks; tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_marker_in_a_test_name_blocks; tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_marker_in_a_trailing_comment_with_quotes_blocks"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The density check compares the prose comment lines in the edit's new text against its old text. A net of zero or
  less passes, so rewording an existing doc comment in a file already over the cap is not denied. A Write counts as
  all new.
- The private-workflow marker rule strips single-line string-literal text from code lines before it looks, so a plan
  fixture such as `"## Phase 1: Build"` in a test passes. Comment lines, and a trailing comment after code, are still
  checked. The stripping lives in `lib/source_text.py` as `without_string_text`.
- The name passed to `it`, `test`, `describe`, `context` and `suite` (also after `.each(...)` or a tagged template) is
  still searched, and a trailing comment is cut off by `split_trailing_comment` before the stripping. Docstring and
  block-comment lines are searched raw, as comment lines.
- The lines that continue a multi-line string held as data are not searched: the lines after an assigned or passed
  triple quote (`x = """`, `f("""`) in a Python file, and after an opening backtick in a slash-style file
  (`source_text.string_data_line_numbers`). A triple quote alone on its line is data when the previous code line ends
  with `(`, `[`, `{`, `,` or `=`, so formatter-wrapped fixtures pass; after a `:` or at module top it is a docstring,
  also with an `r`, `u` or `b` prefix. A backtick inside a quoted string or a `//` comment, and a triple quote inside
  a single-quoted literal, open nothing. The opening line is still searched. The line that closes the string is
  searched only after its closing quote (`source_text.string_data_closing_tails`), so a trailing comment there blocks.
- The deny text now says a comment the task requires stays and is named in the hand-back.

## Evidence

- Five blocks across two sessions on a requested doc-comment correction, with deny text that said to delete it.
- Every plan-format, code-step and dry-run test writes phase headings as strings, so each new test there tripped the
  marker rule.
- Both new tests fail on the base gate and pass after.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
