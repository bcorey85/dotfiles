---
type: "Change"
change_type: "changed"
title: "plan-reading folds into /code and adr-template moves into the adr skill folder"
description: "The phase-scoped plan-reading rule moves word for word into a /code section, and the ADR template moves from _shared into skills/adr, so no _shared file has a single loader."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T13:28:55-06:00"}
seq: 19
kind: "fix"
components: ["skill/code", "skill/adr", "agent/plan-verifier", "shared/plan-format"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_code_skill_carries_the_phase_scoped_plan_read_its_step_two_names"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The rule text of `skills/_shared/plan-reading.md` moves word for word into a new `## Reading a plan` section of `skills/code/SKILL.md`, the one skill that read it (step 2). Its title, its "How a plan is READ" line and its consumer line, which named `coder-core` and `code-reviewer` though neither loads it, are dropped, and the file is deleted. Step 2 points at the new section; `plan-format.md` names the section; `plan-verifier` (claude agent and opencode port) says it is exempt from `/code`'s phase-scoped read.

`skills/_shared/adr-template.md`, read only by `skills/adr/scripts/adr_flow.py`, moves unchanged to `skills/adr/adr-template.md`; the script's default path and `tests/scripts/test_adr_flow.py` follow it. The `ADR_TEMPLATE` override stays.

## Evidence

`rg` over the toolkit finds one loader for each file: `/code` step 2 for plan-reading, `adr_flow.py` for adr-template.

## Result

No `_shared` file except `lane-brief.md`, which every fork reads from its brief, has a single loader. The /code fork no longer spends a Read on a plan run.

## Watch

None.

## Back-out

Revert the commit.
