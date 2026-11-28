---
type: "Change"
change_type: "fixed"
title: "Review finding parser keeps the case list under a colon-ended finding"
description: "A reviewer finding that ends in a colon keeps the case bullets under it, so the fix pass sees every case and no case is filed as an unlocated finding"
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T20:03:32-06:00"}
seq: 5
kind: "fix"
components: ["script/review-loop-findings"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_findings.py::ColonEndedFindingTest::test_section_format_keeps_case_bullets_at_the_lead_indent_and_nested"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- Section format: a located item whose text ends in `:` opens a notes list. The bullets under it, at its indent or
  nested, continue that item until a bullet opens with a file:line, a bullet states an ask in an Ask section, or a
  plain line at the item indent ends the list.
- Tagged-bullet format (the test reviewer): untagged bullets under a colon-ended tagged bullet, at its indent or
  nested, join that bullet instead of being dropped. A deeper untagged bullet joins any tagged bullet as its detail.

## Evidence

A review run skipped a test-gap finding as a false positive: the parser kept the lead line, which ended in a colon,
and dropped the cases listed under it. The tilde line form from the same report already parses located on master.

## Result

New tests in `ColonEndedFindingTest` fail on the old parser and pass now. Full suite passes.

## Watch

None: no intake number reads parser splits.

## Back-out

Revert the commit; the parser splits colon-ended findings as before.
