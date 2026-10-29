---
type: "Change"
change_type: "changed"
title: "plan-reviewer: a new finding class, a class scoped as a list"
description: "plan-reviewer: a new finding class, a class scoped as a list."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/plan-reviewer"]
evidence: ["judgment"]
watches: []
---

## Change

plan-reviewer: a new finding class, a class scoped as a list. The reviewer names the shared property, runs the command that lists every site with it, and reports the omitted sites on an `Enumerated:` line

## Evidence

judgment

### Anchor reasons

Anchor `agents/plan-reviewer.md`, section `## What you look for` (evidence: removal round, judgment, seeded round):

One paragraph per finding class, re-entry, and the enumerate-never-sample rule. Added by judgment, effect unmeasured: a class scoped as a list, where the reviewer names the shared property, runs the command that lists every site with it, and reports the omitted sites on an `Enumerated:` line. The bullets under tree claims (citation decay, batching), the rubber-duck prose, and the settled-decisions line are gone: one plant per class was found in every run without them, and the DUCK pass still ran from the output block alone. Without the bullets the reviewer stayed in the tree instead of scanning the live corpus the plan cited. Phase shape (a phase past about 10 files with no atomic reason, a skeleton that skips Phase 0): a seeded round caught the planted shape defects with it and none without, with no false alarm on a clean plan. The criteria cap was dropped by judgment, because a ticket cannot be split.

## Result

Effect unmeasured.

## Watch

plan defects with `gate_missed` `eng-spec` where the plan named some sites of a shared change and missed others.

## Back-out

delete the paragraph
