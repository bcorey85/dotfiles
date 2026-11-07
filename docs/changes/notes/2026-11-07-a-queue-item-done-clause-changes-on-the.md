---
type: "Change"
change_type: "fixed"
title: "A queue-item done-clause changes on the orchestrator's ruling"
description: "In a /code plan built from a queue item with no ticket, a done-clause criterion changes on the orchestrator's recorded ruling with no typed user sign-off."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T01:28:20-06:00"}
seq: 5
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_a_queue_item_done_clause_criterion_changes_on_the_orchestrator_s_recorded_ruling"
asked: ""
proof: []
unmeasured: ""
---

## Change

The /code sign-off rule covers ticket ACs and eng-spec criteria. A criterion that restates a queue item's done-clause changes on the orchestrator's ruling recorded in the item or brief, logged under `## Plan Deviations`. A brief is still never the user's sign-off for a ticket AC.

## Evidence

judgment: a /code run on two queue items stopped for user sign-off on an orchestrator ruling. The new guidance test fails on the base commit and passes after.

## Result

Guidance test passes; rule anchors check clean.

## Watch

—

## Back-out

Revert the commit's hunks in the named files.

