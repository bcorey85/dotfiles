---
type: "Change"
change_type: "changed"
title: "the last dense rules in coder-core, plan-format, reviewer-calibration and eng-spec become one-branch lists"
description: "coder-core's runner choice, acceptance_criteria and cause rules, plan-format's gate, Agent-run, rg-ban and Expected red rules, reviewer-calibration's plan-is-wrong and cannot-tell branches, 5-decisions step 13's record rules and 6b-review step 20's round rules and step 21's count definitions become lists, one branch per item, with every rule word kept."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T19:36:48-06:00"}
seq: 7
kind: "fix"
components: ["skill/coder-core", "shared/plan-format", "shared/reviewer-calibration", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_prose_facts.py::ToolkitProseFactsTest::test_coder_core_plan_format_calibration_and_eng_spec_rules_are_one_branch_list_items"
asked: ""
proof: []
unmeasured: "Every layout split; the short lead-ins added to carry a split list ('through the first runner that applies', 'Write cause: by what is wrong', 'At a gated phase /code')."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

coder-core: the runner-choice bullet in Verify before you report is a three-item list with the collection-error rule its own bullet; the `acceptance_criteria` and `cause` rules under PLAN-IMPACT findings are two-branch lists. plan-format: the gate rule, the Agent-run tag, the rg ban-or-presence rule and the Expected red rule are lists. reviewer-calibration: the plan-is-wrong branch is a sub-list and the cannot-tell case is a third routing branch. eng-spec 5-decisions step 13's four record rules and 6b-review step 20's round rules and step 21's count definitions are lists.

Kept with no cut, so no meter run:

- coder-core's bug-fix test-first line stays at the top of Readability comes first: its top placement has its own rule-meter scenarios (the `-top` variants), so moving it under Tests are yours changes a measured position.
- reviewer-calibration's "`ask` is not the plan-impact channel" paragraph and the routing-bug sentence overlap; cutting either is a removal round, and the overlap is two sentences.
- plan-format's Close pass rule and the template's Close pass comment both stay: the template line is the shape the rule asks for.
- The earlier 2026-11-22 change already split review-fork-run, 5-decisions step 14, 6b-review step 19b, the goal-blind-researcher repair loop and the spec-research search rules; 4-explore.md no longer holds an invariant survey.

## Evidence

Judgment: each split keeps every rule word; only list markers and short lead-ins are added.

## Result

Each listed paragraph is a list with one branch per item.

## Watch

None.

## Back-out

Revert the commit.
