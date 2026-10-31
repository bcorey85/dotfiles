---
type: "Change"
change_type: "fixed"
title: "A reviewer's notes after a None line are no longer findings"
description: "The review loop's Fix/Ask/Nit parser reads a section that opens with a none line, such as \"None.\", as empty, so the reviewer's notes below it no longer reach a coder as issues or the user as asks."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T13:28:30-05:00"}
seq: 268
kind: "fix"
components: ["agent/review-loop"]
evidence: ["census", "bench run"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_the_notes_after_a_sections_none_line_are_no_findings"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_section_findings` in `review_loop_findings.py` returns no findings for a Fix/Ask/Nit section whose first line
is a none word that ends its sentence: "None.", "None. What I checked:", "N/A — no tests changed". The lines after it
are the reviewer's notes, such as what it checked or why it did not flag something. A first line that only starts with
a none word, such as "None of the three queries filters by tenant:", still lets the findings under it through.

A section that opens with a bare `file:line` paragraph now starts an item only at each bare `file:line` line at that
indent, so the bullets under a paragraph finding stay in it.

## Evidence

A census of 2,532 local transcripts found 34 review sections that open with a none line. Five had notes after it, and
the parser read each note as a finding. In bench /code runs those notes reached the user as asks, which cost an extra
asks round, and reached a coder as issues to fix. In another run, one smell-reviewer finding written as a paragraph
with bullets became four findings.

## Result

The test for notes after a None line parsed them as findings before the change and as none after it. The test for a
paragraph finding parsed four findings before the change and two after it. A third test checks that a section whose
first sentence starts with "None of" keeps its findings. The review loop's 131 tests pass.

## Watch

None; a fix with a test.

## Back-out

Revert `review_loop_findings.py` and the three tests.
