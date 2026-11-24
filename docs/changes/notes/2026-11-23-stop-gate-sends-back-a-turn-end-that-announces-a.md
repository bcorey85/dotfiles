---
type: "Change"
change_type: "added"
title: "Stop gate sends back a turn end that announces a step with nothing started"
description: "The Stop gate now sends a main-session turn back once when its last message says the session will do, or is doing, a step with nothing started, so the session starts the step or says plainly it has not."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T13:26:34-06:00"}
seq: 7
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_announced_step.py::AnnouncedStepTest::test_present_claim_of_work_in_progress_blocks"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`gates/announced_step.py` finds a sentence in the final message with a first-person future or in-progress step
("Next I'll ...", "I'm starting it now", "Starting it now"). `staged_claim_gate.py` adds its reason on Stop, beside the
staged-claim and permission-question reasons. The sentence passes when it names a condition, names the user, opens on
a request before "and I'll", says work runs or is waited on, asks a question, or sits in quotes. A second stop in a row
passes, as before. No new hook process: the check runs inside the existing Stop gate.

## Evidence

Two agent-evals sessions in one day ended a turn announcing work with nothing started, and the user caught both by
hand. The repo's "never sit idle" prose did not stop it.

## Result

Before: the gate passed "Next: I claimed the item and I'm starting it now." After: it blocks it once. 11 new tests
and the 67 staged-claim tests pass; ruff is clean on the three files.

## Watch

None: no intake number counts announced steps. Read the next sessions' Stop blocks for false sends.

## Back-out

Delete `gates/announced_step.py`, the import and the two lines in `staged_claim_gate.py` main(), and
`tests/scripts/test_announced_step.py`.
