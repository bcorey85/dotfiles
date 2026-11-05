---
type: "Change"
change_type: "fixed"
title: "The code skill runs the review for a pure move or rename too"
description: "Step 5 of the /code skill says to run the review for every phase, a pure move or rename too, so a fork does not skip its review loop and leave the commit gate blocked."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T23:55:57-06:00"}
seq: 11
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_code_reviews_every_phase_a_pure_move_too"
asked: ""
proof: []
unmeasured: ""
---

## Change

One sentence in step 5 of `skills/code/SKILL.md`. The `## Instructions` rule-anchor row takes the new hash. The skill has no opencode port: opencode loads `~/.claude/skills/` as is.

## Evidence

judgment: a /code fork judged a refactor a pure move and skipped its review; the commit gate blocked, and the review the orchestrator then ran found a real defect (shared names kept a private underscore prefix). The guidance test fails on the base commit and passes after.

## Result

`test_guidance_rules.py` passes; `rule-anchors.sh check` passes.

## Watch

—

## Back-out

Remove the sentence and restore the anchor row's hash.
