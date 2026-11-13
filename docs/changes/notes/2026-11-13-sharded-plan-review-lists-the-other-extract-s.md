---
type: "Change"
change_type: "fixed"
title: "Sharded plan review lists the other extract's phases and files"
description: "Each half of a sharded plan review now ends with the other half's phase titles and the files they touch, so a shard reviewer stops flagging a gap that the other half fills."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T12:11:07-06:00"}
seq: 1
kind: "fix"
components: ["script/plan-review-shards"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_review_shards.py::PlanReviewShardsTest::test_each_shard_names_the_other_shards_phases_and_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

`plan_review_shards.py cut` appends a `## Phases in the other extract` section to each shard. The section names the full plan path and gives one bullet per omitted phase: its id, its title, and the paths from its Files entries, or `files: none named`. It reads the plan through `plan_format` and adds no regex. The section adds no phase span. It tells the reviewer not to review those phases and to grep the full plan before raising a gap that spans phases.

## Evidence

One sighting: a shard reviewer flagged a missing section as a gap, and a phase in the other shard creates that section. The false gap counted toward the plan-review findings total.

## Result

The new tests fail on the old script (1 failure, 1 error) and pass on the new one (15 of 15). The full suite passes: 3771 tests, 0 failed. The real-plan sweep found no plan over 400 lines on this machine, so no real plan was cut.

## Watch

None. No intake number separates false cross-shard gaps from real ones.

## Back-out

Revert the commit. Shards return to holding only their own phases.
