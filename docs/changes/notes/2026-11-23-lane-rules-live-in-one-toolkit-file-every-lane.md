---
type: "Change"
change_type: "added"
title: "Lane rules live in one toolkit file every lane brief points at"
description: "A forked lane reads how it reports, runs every phase through, records rulings and runs its checks from skills/_shared/lane-brief.md, so the rules survive compaction and no lane stops after a phase to ask for a commit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T10:54:59-06:00"}
seq: 5
kind: "structured"
components: ["shared/lane-brief", "rule/orchestration"]
evidence: ["rule meter", "judgment"]
watches: []
test: ""
asked: ""
proof: ["2026-11-23-lane-brief-run-through-line-makes-a-lane-commit-a"]
unmeasured: "The run-through line ran on one TypeScript fixture; a second fixture is still owed. The reporting, ruling, toolkit-edit, memory-cap and final-report sections restate rules from orchestration.md, the global CLAUDE.md and the agent-evals CLAUDE.md, so they were not metered. No intake number reads lane stalls, since lanes run on this machine only."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Added `skills/_shared/lane-brief.md`: report only to the orchestrator, run every phase through with a commit per
phase, the standing-ruling line form, toolkit-edit duties (change file, rule-meter, anchors), the suite under the
memory cap, and the final report. The orchestration fork rule now tells the brief to point the fork at that file.
`tests/scripts/test_lane_brief.py` checks each heading, the ruling form and the pointer.

## Evidence

Rule meter on the run-through line; judgment for the rest. Lane rules lived in a session scratchpad file; lanes stalled after a phase to ask for a commit until a
run-through line was added, and the file was lost once at compaction and rewritten.

## Result

Rule meter, Opus, 8 runs per arm per prompt level: a lane at a passed phase end commits it or goes on in 6 of 8 with the
line and 1 of 8 without on a neutral prompt, and 5 of 8 against 2 of 8 on a prompt that cites the /code stop rule
(11 of 16 against 3 of 16). A bullet that repeated the report-only rule was cut.

## Watch

None: see `unmeasured`.

## Back-out

`git revert` the commit.
