---
type: "Change"
change_type: "fixed"
title: "review loop keeps finding lines that open with a none word"
description: "The review loop's section parser drops only a bare none marker inside a section, so a finding or a continuation line that opens with None, Empty, N/A or Omitted stays finding text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:56:52-06:00"}
seq: 428
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_line_that_opens_with_a_none_word_after_the_first_finding_is_finding_text"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_findings.NONE_LINE` matches a bare marker only (`None.`, `[n/a]`, `*empty*`), not any line that opens
  with the word.
- A lead-in sentence about none before a section's first item ("None of the three queries filters by tenant:") is
  still skipped, through `NONE_LEAD_IN`.

## Evidence

judgment: a bug hunt on master 22c42b39 found that a Fix bullet "Empty catch in c.py:4 swallows the error" was
dropped, and continuation lines "Empty input reaches `walk`..." and "None of the callers reset `state`..." were cut
from their findings. Over 4441 real reviewer final texts, the old rule skipped one mid-section line, and that line
was a real finding.

## Result

The named test fails before (two findings, both cut short) and passes after (three findings with their full text).
`test_review_loop_script` and `test_change_size_bar`: 207 tests, 0 failed; ruff clean.

## Watch

None. A dropped finding shows as a missing packet row.

## Back-out

Restore the old `NONE_LINE` pattern, drop `NONE_LEAD_IN` and its check, and remove the test.
