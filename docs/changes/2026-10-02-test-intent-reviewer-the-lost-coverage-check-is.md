---
type: "Change"
change_type: "removed"
title: "The test audit now runs cull and weak-assertion checks only"
description: "The test-intent reviewer now runs cull and weak-assertion checks only, without the lost-coverage check."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 15
kind: "behavior"
components: ["agent/test-intent-reviewer", "skill/test-audit"]
evidence: ["census"]
watches: []
---

## Change

The test-intent reviewer now runs cull and weak-assertion checks only, without the lost-coverage check. The test audit's receipt and log row drop the lost-coverage count and base-suite size

## Evidence

census

## Result

Work logs, dotfiles and agent-evals sessions excluded: 0 lost-coverage findings in 15 test audits, while the same audits found 67 weak assertions and 53 culls. Saves the deleted-test search on every audit; the token cut is not measured.

## Watch

—

## Back-out

restore the two agent copies and the test-audit and branch-recap skills from git
