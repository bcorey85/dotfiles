---
type: "Change"
title: "The mutation tester's precondition list now starts with \"The dispatch does not state a test command → stop"
description: "The mutation tester's precondition list now starts with \"The dispatch does not state a test command → stop and say so."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 6
components: ["agent/mutation-tester"]
evidence: ["seeded round"]
watches: []
---

## Change

The mutation tester's precondition list now starts with "The dispatch does not state a test command → stop and say so. Never infer one from the repo.", and its heading count reads five.

## Evidence

seeded round

### Anchor reasons

Anchor `agents/mutation-tester.md`, section `## What your dispatch must contain` (evidence: removal round):

Target plus exact mutation, expected killer, and test command; stop on a missing item. The missing-test-command stop is enforced from the Step 0 list, not here.

Anchor `agents/mutation-tester.md`, section `## Step 0 — Preconditions (all five, before touching anything)` (evidence: seeded round):

The missing-test-command stop comes first because the agent runs this list and skips the dispatch-contents section: as a bullet here it stopped six of six times, and as a sentence in that section two of six. Repo, lock, and target checks, then the green-baseline rule and the executed-test count. Kept: "A previous run mutated a file and never restored it". Without it, and the uncommitted-work reason in Step 4, the agent took a real uncommitted edit in the target for a leftover mutation and stopped in two of twelve runs.

## Result

The same rig with a dispatch that omits the test command, and the killed and survivor shapes with the command present. The live text guessed a command and mutated in three of three runs. The same rule as a sentence in the dispatch-contents section stopped two of six. As the first precondition bullet it stopped six of six with no edit to the target, and the six runs with the command present gave the right verdict with a hash-verified restore every time.

## Watch

—

## Back-out

—
