---
type: "Change"
change_type: "removed"
title: "The Agent model line leaves orchestration: the model guard alone keeps opus off the call site"
description: "The Delegation bullet about the Agent model values is removed, because it did not stop an explicit opus request with or without it; the model guard denies that pin."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T00:00:00-06:00"}
seq: 38
kind: "structured"
reverts: "2026-11-22-orchestration-names-the-agent-model-values-the"
components: ["rule/orchestration"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-22-the-agent-model-line-sends-no-opus-or-inherit-pin"]
unmeasured: "No intake number counts Agent calls by call-site model value."
---

## Change

The bullet under `### Delegation` in `orchestration.md` that named the Agent `model` values the hook passes and denies is deleted, and the Delegation anchor row in `docs/rule-anchors.md` goes back to its earlier text. `agent-model-guard.sh` still denies `opus` and `inherit` at the call site; nothing about the guard changes.

## Evidence

Rule meter scenario AM01 (a design judgment dispatched to general-purpose, 20 runs on opus): 0 of 10 on-arm and 0 of 10 off-arm runs pinned opus or inherit. Scenario AM02 tempts the pin: a review dispatched to general-purpose, which has no pinned agent file, with a task that asks for the strongest model, opus. Run on the default model, neutral level, 3 runs per arm: on arm 3 violated, 0 complied, 0 NO_TEST; off arm 3 violated, 0 complied, 0 NO_TEST; every run pinned opus. Off equal to on, so the rule meter reads NO-EFFECT.

## Result

The line does not stop an explicit opus request; the hook denies it. On equals off, so the line has no effect and does not ship. AM01 shows the model sends no pin unprompted. The line is removed.

## Watch

None.

## Back-out

Restore the bullet to `orchestration.md` and the rehashed row in `docs/rule-anchors.md`.
