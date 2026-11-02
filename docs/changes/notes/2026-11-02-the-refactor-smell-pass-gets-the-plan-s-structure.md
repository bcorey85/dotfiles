---
type: "Change"
change_type: "fixed"
title: "The refactor smell pass gets the plan's structure and files plan-structure findings as asks"
description: "A branch audit's smell-reviewer prompt now carries the files the branch's plan names and its Plan Deviations lines, and a finding against them is an ask the user answers, so the closing refactor pass no longer removes structure a phase review had a coder add."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T14:57:13-06:00"}
seq: 9
kind: "fix"
components: ["skill/refactor", "script/plan-format"]
evidence: ["transcript read"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest.test_branch_prep_hands_the_plan_structure_and_deviations_to_the_smell_reviewer"
asked: ""
proof: []
unmeasured: ""
---

## Change

`plan_format.required_structure` returns the paths a plan's phases name in their `**File**:` / `**Files**:` entries and the non-blank lines of its `## Plan Deviations` section.

`refactor_flow.py branch-prep` finds each plan under `docs/plans/*/spec.md` that the branch adds or changes, reads it at the head ref, and prints a `## Plan-required structure` block inside the smell-reviewer prompt: the named files, the deviation lines, and the rule that a finding that removes or reshapes them goes under `### Ask` with a `[plan-structure]` tag. Its `NEXT:` line sends every `### Ask` finding to the user and says to log a tagged one with `plan_structure: true`.

`log` refuses a finding with `plan_structure: true` unless it has `disposition=ask` and is not `actioned=fixed`. The refactor skill's step 3c says the same. A branch with no plan prints no block.

## Evidence

On two tickets, a phase review called missing package re-exports plan drift and a coder added them; the closing `/refactor +deep` pass then called the same re-exports half-used and a coder removed them. The smell prompt carried no plan text.

## Result

The three new tests fail on the old script (4 failures) and pass on the new one. Over the 1259 plans under `~/dev`, 1166 give at least one named file and 971 give deviation lines; none fail to parse.

## Watch

None.

## Back-out

Revert the commit: drop `required_structure`, the plan block in `branch-prep`, and the `plan_structure` check in `log`.
