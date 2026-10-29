---
type: "Change"
change_type: "changed"
title: "eng-spec stops before handoff when the criteria file was never written"
description: "plan check gains --final, which also fails a spec with an Acceptance Criteria section whose acceptance-criteria.md is missing or empty and names the spec-criteria step; eng-spec's handoff runs it before it reports the plan saved."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:53:23-05:00"}
seq: 103
kind: "fix"
components: ["skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_spec_ac_check.py::FinalPlanCheckTest::test_final_check_fails_a_spec_whose_criteria_file_is_missing_and_names_the_step"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step.py plan check --final <spec>` runs every plan check row plus one more: the spec has an Acceptance
  Criteria section and the criteria file beside it is missing or empty. The row names the step that never ran
  (dispatch spec-criteria) and says never to write the file by hand.
- Plain `plan check` is unchanged, because eng-spec runs it on the spec before the criteria file exists.
- eng-spec's handoff phase runs the final check first. Exit 1 is an unresolved planning gate: no "Plan saved".

## Evidence

- A headless eng-spec run reported its spec final with a passing plan check, but spec-criteria never ran. `/code`
  start stopped on the missing file, and the orchestrator sent the worker back by hand. A sibling run the same day
  wrote the file, so the skip is intermittent.
- The test fails on the base tree.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
