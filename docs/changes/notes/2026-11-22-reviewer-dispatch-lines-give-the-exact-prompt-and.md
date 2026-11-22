---
type: "Change"
change_type: "fixed"
title: "Reviewer dispatch lines give the exact prompt and say who writes the report"
description: "Each reviewer dispatch line quotes the Agent prompt word for word and names who writes the report, so no reviewer is told to write a file it cannot."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 26
kind: "fix"
components: ["script/reviewer-dispatch", "script/code-wait", "skill/code"]
evidence: ["review-loop-reviewer-agents-cannot-save-their"]
watches: []
test: "tests/scripts/test_reviewer_dispatch.py::ReviewerDispatchTest::test_the_line_gives_the_exact_prompt_and_the_note_it_was_given"
asked: ""
proof: []
unmeasured: ""
---

## Change

`reviewer_dispatch.request_lines` gives `prompt "Read <prompt file> whole and do that task."` and takes a writer note from its caller: `code_wait.py review` for a code fork, the main session for `reviewer_dispatch.py wait`.

## Evidence

A code fork told reviewers to write their report to a file. The reviewers have no Write tool, so it sent coders to save the reports and later ran reviewers as general-purpose.

## Result

ReviewerDispatchTest in `test_reviewer_dispatch.py`.

## Watch

None.

## Back-out

Revert the commit.
