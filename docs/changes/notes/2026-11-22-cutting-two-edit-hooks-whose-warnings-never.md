---
type: "Change"
change_type: "removed"
title: "Cutting two edit hooks whose warnings never reached the model drops two Python starts per edit"
description: "The rationale-and-path prose check and the reviewer calibration heading check ran after every Write or Edit but exited 0, so their output showed only in transcript view; removing them saves about 70 ms of hook time per edit with no change in what the model sees."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T23:31:57-06:00"}
seq: 43
kind: "user-rule"
components: ["shared/hooks"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-22: deletion and simplification is a priority equal to additions; cut what does not earn its cost"
proof: []
unmeasured: "A removed hook that never reached the model leaves no work-log number to watch; hook latency per edit is the only change."
---

## Change

Removed two PostToolUse `Write|Edit` hooks: `scripts/gates/dead_prose_gate.py` (banned rationale and hard-coded paths
in agent, skill and command files) and `scripts/gates/calibration_refs_guard.py` (a reviewer agent naming a missing
calibration heading). Both registrations leave `settings.json`; the calibration guard's own `Write|Edit` block goes
whole. Their tests go, their rows leave `test_review_fixes.py` and `test_toolkit_self_location.py`, and the
claude-doctor check that only reported whether the calibration guard had anything to guard goes too.

## Evidence

Census. Both hooks always exit 0, one writing to stderr and one to stdout. On PostToolUse that output shows only in
transcript view, never to the model. Fire counts from this machine's sessions since 2026-10-23, toolkit repos left
out: 80,708 fires each, 0 with output the model saw. Work hook-block rows name neither. Banned rationale and sediment
are covered by the toolkit-writing skill; a renamed heading in a prompt file shows in `rule-anchors.sh check`.

Hook time on one Edit payload, median of 15: bare Python start 10 ms, `dead_prose_gate.py` 37 ms,
`calibration_refs_guard.py` 35 ms.

## Result

Each Write or Edit runs two fewer processes, about 70 ms less hook time. The model's view is unchanged.

## Watch

None: see `unmeasured`.

## Back-out

`git revert` the commit; both scripts and their tests come back with their registrations.
