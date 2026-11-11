---
type: "Change"
change_type: "fixed"
title: "The code skill description lets main run the relay's re-review line"
description: "The /code description told the main session to say the stop word for word and make no other tool call; it now also allows running the `To go on:` line the relay gives, so the relay's re-review rule is not overridden."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T19:52:00-06:00"}
seq: 7
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_code_stops_end_as_statements_asks_are_decided_and_main_relays_with_no_tool_call"
asked: ""
proof: []
unmeasured: ""
---

## Change

`skills/code/SKILL.md` description: "say the fork's stop word for word and make no other tool call" gains ", or run the `To go on:` line it gives". `tests/scripts/test_guidance_rules.py` pins the new phrase; `docs/rule-anchors.md` carries the new anchor.

## Evidence

judgment: `code_relay.py` now prints a rule to run the stop's `To go on:` line when the tree changed after a converged review; the old description forbade any other tool call, which contradicts that rule. Unmeasured: the rule-meter has no scenario that stages a /code stop and a relay re-review rule, so no on/off arm grades whether main runs the `To go on:` line.

## Result

—

## Watch

—

## Back-out

Revert the description phrase, the test assertion and the rule-anchors row.
