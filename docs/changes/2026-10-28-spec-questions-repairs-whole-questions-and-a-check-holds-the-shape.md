---
type: "Change"
title: "spec-questions repairs whole questions, and a check holds one question per line"
description: "A new questions_check.py fails a questions file with a clause cut short before `?`, two questions on one line, a wrapped question or a numbering gap; spec-questions runs it after every write, and goal-blind-researcher applies the leak check's own rewrites after two cycles instead of returning UNRESOLVED."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T20:00:00-05:00"}
seq: 175
kind: "fix"
components: ["agent/spec-questions", "agent/goal-blind-researcher", "script/questions-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_questions_check.py::QuestionsCheckTest::test_two_questions_on_one_line_fail"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/tools/questions_check.py check <file>`: each question sits on one line as `N. <question>?`, numbered
  in order, with no `and ?`, `, ?` or ` ?` left by a deleted clause and no second numbered question after a `?`.
- spec-questions runs the check after every write and repair, replaces each flagged question's whole line, and
  applies a leak-check rewrite word for word when the dispatch says so.
- goal-blind-researcher, still flagged after two cycles, re-dispatches spec-questions once to apply the leak check's
  rewrites, then runs research. It returns UNRESOLVED only for a flag with no rewrite.
- The opencode ports carry the same lines.

## Evidence

- A repair deleted a clause in place, leaving a question ending in "and ?", and merged two numbered questions onto
  one line. The leak check flagged the broken question, and the run ended UNRESOLVED with research not run.
- The check over 56 real questions files on this machine passes 54. One real file holds the merged shape (`?7.`).
  The other holds questions wrapped over several lines, from an eval run.

## Result

- A broken repair fails at the write, and a run whose only remaining flags carry the leak check's rewrite goes on to
  research.

## Watch

—

## Back-out

Revert the commit.
