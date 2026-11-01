---
type: "Change"
change_type: "fixed"
title: "Test-reviewer reports in the tagged-bullet form the review script parses"
description: "The scripted review loop reads test-reviewer findings without a model call: the report template now writes top-level `- fix:`, `- ask:` and `- nit:` bullets, so the Sonnet disposition call that classified each test-reviewer report is no longer needed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:28:52-05:00"}
seq: 423
kind: "user-rule"
components: ["agent/test-reviewer", "agent/review-loop"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-01: after the overnight cut-candidate report: fix everything"
proof: []
unmeasured: ""
---

## Change

- `agents/test-reviewer.md`: findings are top-level tagged bullets matching `TAGGED_BULLET` in `scripts/review/review_loop_findings.py`; ask bullets carry `— change:`. The `## Test Review Report` and `###` topic headings stay because `review_loop_gate.py` keys on them. The backticked `nit` in the hygiene heading goes, because the parser's stray-tag check would send the report to the disposition fallback.
- `tests/scripts/test_review_loop_script.py`: `test_a_report_in_the_test_reviewer_template_form_parses_with_no_disposition_call` feeds a template-form report through `parse_review`.

## Evidence

Local loop logs (a test guide, not work evidence) showed 151 Sonnet disposition calls against 134 test-reviewer calls: nearly every test-reviewer report fell back to a model call.

## Result

`test_review_loop_script` passes (196 tests); full dotfiles suite 2,923 tests, 0 failed.

## Watch

None: the work intake does not count disposition calls by reviewer.

## Back-out

Revert the commit.
