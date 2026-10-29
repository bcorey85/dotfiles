---
type: "Change"
change_type: "changed"
title: "The plan reader now treats every factual assertion a plan makes about the repository as unverified and runs"
description: "The plan reader now treats every factual assertion a plan makes about the repository as unverified and runs the command that settles it; resolves every cited path, line number, rule number, section heading and cross-document reference against the tree as it currently stands."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/plan-reviewer"]
evidence: ["escape ranking + bench coverage"]
watches: []
---

## Change

The plan reader now treats every factual assertion a plan makes about the repository as unverified and runs the command that settles it; resolves every cited path, line number, rule number, section heading and cross-document reference against the tree as it currently stands; and reports a document that contradicts itself — one clause corrected with its pair left standing, two clauses that cannot both be satisfied, or the same quantity stated two ways in two places. A claim whose subject is outside the tree it must mark as doubted rather than settled. Its opening premise, which told it factual claims had already been checked, was removed: only the runnability of the verification commands had been.

## Evidence

escape ranking + bench coverage

## Result

The defects that survive planning and surface later are mostly not design errors — they are sentences about the tree that were wrong when written. A constraint calling a symbol dead that has test callers, a verification step naming members of the wrong file, a scope list missing a member a sweep would have found, a stated count that is some other number, a cause attributed to the wrong change. Read from the same lens scored against escaped defects, this discipline is aimed at nearly nine-tenths of that class — far more than it reaches when pointed at code comments, which is where it was derived and where the expectation had been. Citations are the quiet half: a renumber, rename or deletion anywhere silently falsifies every reference to it, and nothing in the lane was resolving them. The removed premise mattered most of all, because it was telling the plan's only adversarial reader that this work had already been done for it. Whether the reader catches what it is now aimed at is unmeasured and not measurable where the change was made; the coverage is a ceiling on the yield, not a prediction of it.

## Watch

—

## Back-out

—
