---
type: "Change"
change_type: "removed"
title: "`code-reviewer` covers security and query cost on every pass, with no specialist reviewers"
description: "`code-reviewer` covers security and query cost on every pass; the specialist reviewers, their Opus copies, the phase `(reviewers: …)` tag and the specialist flags are gone."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 7
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["census"]
watches: []
---

## Change

`code-reviewer` covers security and query cost on every pass, with no specialist reviewers. The security and query-cost specialist reviewers are removed, with their Opus copies. Also removed: the `(reviewers: …)` tag on plan phase lines, the `+sec`, `+perf`, `+smell` and `no-specialist` flags, and the shared trigger file. `code-reviewer` covers security and query cost on every pass

## Evidence

census

## Result

At work, the security reviewer ran 2, 3, 5, 2 and 0 times in five weeks. The query-cost reviewer ran 0 times since Aug 31. Work escapes show 0 security-class and 0 query-cost-class defects. No dispatch site remains.

## Watch

security-class and query-cost-class escape rows.

## Back-out

restore the five files, the plan tag rule and the flags from git
