---
type: "Change"
change_type: "changed"
title: "The general-purpose body is cut to the four behavior-changing lines"
description: "The claude general-purpose agent body keeps four lines (edit over create, docs only when asked, absolute paths with no code recap, report what was verified); the opencode port keeps the same four in its own wording."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T18:00:00-06:00"}
seq: 27
kind: "fix"
components: ["agent/general-purpose"]
evidence: ["rule meter"]
watches: []
test: "tests/scripts/test_toolkit_prose_facts.py::ToolkitProseFactsTest::test_general_purpose_body_is_four_lines_and_keeps_the_report_rule"
asked: ""
proof: []
unmeasured: ""
---

## Change

The claude body is now exactly the four lines that change behavior. The intro, the strengths list and the search guidelines are gone. The opencode port keeps its frontmatter and its own phrasing of the same four rules (a reword: its capitalised NEVER/ALWAYS lines stay as they were).

## Evidence

Rule-meter arms ran on the removed text (old lines 7-18) before the cut, one run per cell, scenario toolkit copy with the old body. GP01 (extend not copy): supportive on 1/1 and off 1/1, neutral on 1/1 and off 1/1, competing on 1/1 and off 1/1. GP02 (red test kept): the same, 1/1 in every cell. Compliance is the same with the text on and off, so no loss was seen at one run per cell. GP01 and GP02 are retired from the scenarios file with the cut.

## Result

Frontmatter plus four body lines in both trees.

Final text, 2026-11-23, the four lines as the on arm and an empty body as the off arm, one run per cell, sonnet: GP01F
with the lines 3/3, without 3/3 (supportive 1/1 against 1/1, neutral 1/1 against 1/1, competing 1/1 against 1/1);
GP02F the same, 3/3 against 3/3. ALREADY on both. The four lines were in master before this branch, so they are kept
and named in one agent-evals removal-round item with the review-fork-run `--by session` bullet; the ruling is in the
plan's decision log (agent-evals-c3, 2026-11-23).

## Watch

Run a new scenario against the old body if the loss of a rule is suspected.

## Back-out

Restore the old body from commit f5fcae9f2.
