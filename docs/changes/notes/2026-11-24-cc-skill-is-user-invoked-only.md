---
type: "Change"
change_type: "changed"
title: "cc skill is user-invoked only"
description: "The nvim comment skill leaves the model's always-loaded skill list and keeps a one-line slash-menu description, so every session stops paying for a description the model never loads on its own (0 of 32 asks under live settings)."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T23:41:30-06:00"}
seq: 7
kind: "structured"
components: ["skill/cc"]
evidence: ["trigger census"]
watches: []
test: ""
asked: ""
proof: ["2026-11-24-the-model-never-loads-the-nvim-comment-skill-on"]
unmeasured: "No intake number counts how often the model loads cc on its own; the user reaches it by typing /cc."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`skills/cc/SKILL.md` gains `disable-model-invocation: true`, and its description drops from a 60-word trigger list
to one sentence for the slash menu. The model no longer sees cc in its Skill list; `/cc` still runs.

## Evidence

Trigger census: under live settings the model loaded cc on its own in 0 of 32 nvim-comment asks (two repos, 8 runs per
ask per repo); with the competing plugin turned off it reached 3 of 12 in one repo (finding 2026-11-23-skill-overrides-cannot-turn-off-a-plugin-skill-and). The fix skill's description and its bare-run step only point
the user at `/cc`; nothing loads cc through the Skill tool.

## Result

A headless probe with a copy of the edited skill as a project skill: the model listed the copy without the flag and
did not list the copy with it, and both stayed in the init event's slash commands. `docs/rule-anchors.md`
now anchors cc's four blocks; `rule-anchors.sh check` passes.

## Watch

None: see unmeasured.

## Back-out

Remove `disable-model-invocation: true` and restore the trigger-list description.
