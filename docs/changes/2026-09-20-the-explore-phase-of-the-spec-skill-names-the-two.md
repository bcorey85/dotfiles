---
type: "Change"
title: "The explore phase of the spec skill names the two planner agent types in the step that launches them"
description: "The explore phase of the spec skill names the two planner agent types in the step that launches them, the way the architecture skill already does."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 21
components: ["skill/eng-spec", "skill/eng-arch"]
evidence: ["census", "judgment"]
watches: []
---

## Change

The explore phase of the spec skill names the two planner agent types in the step that launches them, the way the architecture skill already does. It named them by role only. The user decided the edit.

## Evidence

census, judgment

## Result

A session that runs the spec skill reads the type name in the step that orders the dispatch, so the planner descriptions carry no routing load inside that skill. A census of this machine's top-level dispatches, a guide only, found one first pick of a planner where no prompt and no loaded skill text named the type: the session took the name from always-loaded menu text. It was this step. The planner descriptions were cut on the same day, so this was the one step where a shorter menu could cost a dispatch. No gain in speed or quality is measured. The cost is two type names in a phase file that loads only when the spec skill reaches that phase. The edit removes one of the three reasons in the row above for the guard in the planner descriptions. The other two stand, so the guard stays. Live check: the watch of the row above, at the first intake from the work machine after the change is pulled there. In the work logs, no week with a spec-skill run lacked a backend planner dispatch, 0 of 10. If that alarm fires, back out the description line first, because this edit only adds a name.

## Watch

—

## Back-out

restore the old line.
