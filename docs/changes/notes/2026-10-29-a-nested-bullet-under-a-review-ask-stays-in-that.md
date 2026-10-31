---
type: "Change"
change_type: "fixed"
title: "A nested bullet under a review ask stays in that ask"
description: "The review loop's Fix/Ask/Nit parser starts an item only at a marker as shallow as the section's first marker, so one ask with nested bullets reaches the user as one ask."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T10:10:44-05:00"}
seq: 251
kind: "fix"
components: ["agent/review-loop"]
evidence: ["bench run"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_an_ask_with_nested_bullets_and_a_trailing_paragraph_parses_as_one_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_section_findings` in `review_loop_findings.py` takes the indent of the section's first item marker. A marker
indented deeper is a sub-bullet: its text joins the item before it, as plain continuation lines already did.
`section` no longer strips the indent of the body's first line, so items that are all indented alike under the
heading still split.

## Evidence

In a bench /code run, one code-reviewer ask had a header line, two nested bullets and a paragraph with the question and
the change. It became 3 asks, the first proposed a copy of its own text as its change, and the review rows logged 3
asks for 1.

## Result

The new test parsed that shape as 3 asks before the change and as 1 ask, with its own question and change, after it.
A second new test checks that asks indented alike under the heading stay separate.

## Watch

None; a fix with a test.

## Back-out

Revert `review_loop_findings.py` and the two tests.
