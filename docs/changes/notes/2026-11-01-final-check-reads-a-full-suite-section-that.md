---
type: "Change"
change_type: "fixed"
title: "Final check reads a Full suite section that documents CI"
description: "A repo whose CLAUDE.md documents CI as its full suite in a Full suite section no longer stops the final check when its check-only command prints no test summary."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:16:34-06:00"}
seq: 426
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_full_suite_section_that_documents_ci_counts_as_the_marker_line"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; the stop it removes is rare and no intake number reads it."
---

## Change

The final check also treats a heading that names the full suite, with CI named in the heading or the prose under it, as the line `Full suite: CI`. No count parsing.

## Evidence

judgment: one run stopped on a check-only quality command and needed a manual CLAUDE.md edit and a resume.

## Result

The check-only command of such a repo passes as `passed (check only; CI runs the full suite)`. A Full suite section that does not name CI still runs as before.

## Watch

—

## Back-out

Revert the commit.

