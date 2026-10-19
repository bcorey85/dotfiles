---
type: "Change"
title: "The security and query-cost specialist reviewers are removed, with their Opus copies"
description: "The security and query-cost specialist reviewers are removed, with their Opus copies."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 7
components: ["agent/code-reviewer"]
evidence: ["census"]
watches: []
---

## Change

The security and query-cost specialist reviewers are removed, with their Opus copies. Also removed: the `(reviewers: …)` tag on plan phase lines, the `+sec`, `+perf`, `+smell` and `no-specialist` flags, and the shared trigger file. `code-reviewer` covers security and query cost on every pass

## Evidence

census

## Result

At work, the security reviewer ran 2, 3, 5, 2 and 0 times in five weeks. The query-cost reviewer ran 0 times since Aug 31. Work escapes show 0 security-class and 0 query-cost-class defects. No dispatch site remains.

## Watch

security-class and query-cost-class escape rows.

## Back-out

restore the five files, the plan tag rule and the flags from git
