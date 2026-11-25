---
type: "Change"
change_type: "changed"
title: "A capped review's asks are ruled with no coder and applied on resume"
description: "The code skill's cap-reached step rules the packet's finding asks through `phase_asks.py` and dispatches no coder, then stops; the resume applies each accepted capped ask through `review_fix.py launch --fix`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-24T14:10:00-06:00"}
seq: 3
kind: "fix"
components: ["skill/code", "script/phase-asks"]
evidence: ["tests/scripts/test_phase_asks.py", "tests/scripts/test_review_asks.py"]
watches: []
test: "tests/scripts/test_phase_asks.py::FreshRunDropsARejectedAskTest"
asked: ""
proof: []
unmeasured: "No rule-meter on/off run covers a cap-reached packet that carries asks: no scenario fixture reaches the cap with asks open, so the two sentences have no arm. The script tests pin the ruling and the ruler word; the skill text only routes to them."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

At `cap-reached`, the code fork runs `phase_asks.py list`, rules each ask as for `converged`, dispatches no coder for an accepted ask, and then stops. The resume applies each accepted capped ask through `review_fix.py launch --fix`. The present-asks text and the stop text now name the `--by` ruler from the same function that prints the asks-done line.

## Evidence

`test_phase_asks.py` pins the cap-reached ruling path. `test_review_asks.py::AsksDoneGuidanceTest` pins the ruler guidance.

## Result

Before, a cap-reached stop dropped the packet's asks unruled; now each is ruled before the stop and applied on resume.

## Watch

—

## Back-out

Revert the `cap-reached` bullet and the Resume sentence in the code skill, and `asks_done_guidance` in `review_asks.py`.
