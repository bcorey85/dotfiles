---
type: "Change"
change_type: "fixed"
title: "Plan review cuts its shards outside the plan folder"
description: "An eng-spec plan over 400 lines now gets its two review extracts from a script that writes them to a temp folder and deletes it after the hand-backs, so no stale review-shard copy is left in the plan folder for a later coder lane to treat as its own."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T04:34:27-06:00"}
seq: 432
kind: "fix"
components: ["skill/eng-spec", "script/plan-review-shards"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_plan_review_shards.py::PlanReviewShardsTest::test_a_long_plan_cuts_two_shards_outside_the_plan_folder"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/tools/plan_review_shards.py`. `cut <spec.md>` prints the plan's own path for a plan of at most 400 lines or fewer than two phases; otherwise it writes shard A and shard B to a new temp folder and prints both paths. Each shard holds every line outside a phase section plus its half of the phases, split at the phase boundary nearest the midpoint. Phase sections come from `plan_format.phase_spans`, and a phase id with two sections stops the cut. `clean <folder>` deletes a folder `cut` made and refuses any other.
- The fresh-eyes review step in eng-spec calls `cut` in place of a hand-cut `sed` extract written to the task folder, and calls `clean` once both hand-backs are written. The `review-round<n>-shard-<x>.md` reports stay in the task folder for round 2.

## Evidence

- A code review found per-shard spec copies (review-shard-a.md, review-shard-b.md) left untracked in a plan folder after plan review; a later coder lane treated them as owned files and they went stale against the plan.

## Result

- The new tests fail before the change (8 of 8: no script) and pass after.
- Over every plan under ~/dev (447): 0 errors, 364 cut into two shards, 83 reviewed whole; no shard folder left behind.

## Watch

None: no intake number counts files left in a plan folder.

## Back-out

Revert the commit; the skill step returns to the hand-cut extract.
