---
type: "Change"
change_type: "changed"
title: "A required audit in the diff reviewer that reads every guard, filter, lint rule, validation check, tolerance"
description: "A required audit in the diff reviewer that reads every guard, filter, lint rule, validation check, tolerance, exception handler and equality predicate the change touches against the contract it claims to enforce — its own name, docstring, rule id, the documented meaning of a config key."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["escape ranking + bench coverage"]
watches: []
---

## Change

A required audit in the diff reviewer that reads every guard, filter, lint rule, validation check, tolerance, exception handler and equality predicate the change touches against the contract it claims to enforce — its own name, docstring, rule id, the documented meaning of a config key, or a stated invariant — and demands one concrete input that satisfies the code while violating that contract, or an explicit statement that none exists. Covers both directions: too narrow lets a violation through, too wide rejects what the contract permits or fails work the check was never meant to judge. Names the recurring shapes as well — a handler that returns its unexamined input is a check failing open, a condition that cannot be false on the population it runs against is satisfied vacuously, and a written claim about behavior that disagrees with the code is a finding even when the code is the correct half.

## Evidence

escape ranking + bench coverage

## Result

Bugs reaching the pull request were being found there by a bot rather than by the loop, at roughly a third of all the bugs the loop saw in the same period, and they shared one shape: a check whose behavior is narrower or wider than the invariant it advertises. Diff review was missing them structurally, because the defect is not in the diff — it is in the gap between the changed check and a contract stated somewhere else in the tree, so nothing about reading the diff more carefully would surface it. Scored against that population before shipping, the audit is aimed at two thirds of them, and at three quarters of a separate set of escaped bugs it had never been shown; what it does not reach is concurrency with no invariant written down, checks that are simply absent, and documentation that is wrong about correct code. That last group is the larger remaining bucket and wants its own instrument rather than a wider version of this one. Whether the audit actually catches what it is aimed at is unmeasured and not measurable where the change was made — the repositories that produced these defects are not on that machine and no pre-change tree exists to replay, so the coverage figure is a ceiling on the yield and not a prediction of it.

## Watch

—

## Back-out

—
