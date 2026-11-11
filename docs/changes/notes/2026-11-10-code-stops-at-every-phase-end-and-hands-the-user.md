---
type: "Change"
change_type: "changed"
title: "Code stops at every phase end and hands the user the commit line"
description: "/code no longer goes on to the next phase by itself: every phase end stops for the user's read, and the stop names the commit line to run after reading and staging, so phases no longer pile up uncommitted."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-10T17:04:07-06:00"}
seq: 4
kind: "user-rule"
components: ["skill/code"]
evidence: ["peer report", "user request"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_code_stops_at_every_phase_end_and_hands_the_user_the_commit_line"
asked: "2026-11-10: \"it shouldnt commit by itself. it should stop to let me review but prompt me when commit needs to run\" ... \"ship it\" ... \"but read first\""
proof: []
unmeasured: "No run of either arm: the rule meter runs one coder or reviewer on a small plant and has no fixture that runs /code across a phase boundary, so it cannot grade this step. No intake number counts commits per phase. The user was told before it shipped."
---

## Change

`skills/code/SKILL.md`:

- A low-risk phase with every machine gate green now stops for sign-off like every other phase. The auto-advance
  block is gone.
- The run never commits. The sign-off block's next steps are: read the queue, stage what you have read, then run the
  commit line it prints (`! git commit -m "<subject>"`), then start the next phase. The last-phase block carries the
  same commit line.
- The subject is the phase's `Commit` line in the plan, else the ticket id and the phase title.
- The opening rule no longer lists the next phase and a commit among the steps the run takes without stopping.

## Evidence

peer report: a multi-phase run reached its third phase with the first two uncommitted, because the run went on by
itself and no step named a commit. user request: the user ruled that the run stops for their read and prompts them
for the commit.

## Result

The test fails before the edit and passes after it; it pins the wording only. Whether a /code run stops and prints
the line is not measured: see `unmeasured`. `bash tests/run.sh` passes.

## Watch

None: see `unmeasured`. Expect more stops per plan: one per phase, where low-risk phases ran on before.

## Back-out

Restore decision rule 6 and the auto-advance block in `skills/code/SKILL.md`, remove the commit lines from the two
stop blocks, and restore the two anchor rows.
