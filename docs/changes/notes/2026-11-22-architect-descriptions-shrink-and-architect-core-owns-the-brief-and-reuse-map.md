---
type: "Change"
change_type: "changed"
title: "Architect descriptions shrink to the dispatch sentence and architect-core owns the exploration brief and the Reuse Map rules"
description: "The backend and frontend architect descriptions name the design scope and the /eng-spec phase 4 dispatcher; architect-core holds the seven-item exploration brief, the invariant survey as a list, and the Reuse Map seed and gate rules; the phase 4 prompt and both architects point to it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T17:00:00-06:00"}
seq: 26
kind: "fix"
components: ["skill/architect-core", "skill/eng-spec", "agent/backend-architect", "agent/frontend-architect"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_prose_facts.py::ToolkitProseFactsTest::test_architect_core_owns_reuse_map_rules_and_brief_and_agents_do_not_repeat"
asked: ""
proof: []
unmeasured: "Description cuts and the relocation of the brief and Reuse Map rules into architect-core; no rule-meter arm carries them."
---

## Change

Both architect descriptions read "Designs ... as plans for the coder. Dispatched by /eng-spec phase 4." in the claude agents and the opencode ports. architect-core Two-Stage Dispatches now holds the seven-item exploration brief with the invariant survey as a list of branches, and the Exception clause. architect-core gains a Reuse Map section with the seed and justification-gate rules. The phase 4 prompt points to the brief, and each architect's Reuse Map placeholder points to the architect-core rules. Both opencode ports gain a first-action line that reads the architect-core skill, because opencode does not preload skills.

## Evidence

The Reuse Map rules lived in four files (both architects and both ports); the brief lived in the phase 4 prompt.

## Result

One owner for the brief and one for the Reuse Map rules; the descriptions name the dispatcher.

## Watch

None.

## Back-out

Revert the commit.
