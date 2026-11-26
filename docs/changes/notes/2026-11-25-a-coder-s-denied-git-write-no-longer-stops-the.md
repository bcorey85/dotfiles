---
type: "Change"
change_type: "fixed"
title: "A coder's denied git write no longer stops the code run"
description: "The /code skill keeps stage and commit steps out of a coder's prompt, so no coder makes the git write that the gate denied and the fork stopped on."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T18:33:00-06:00"}
seq: 6
kind: "fix"
components: ["skill/code"]
evidence: ["tests/scripts/test_code_skill_text.py"]
watches: []
test: "tests/scripts/test_code_skill_text.py::CodeSkillTextTest.test_a_coder_prompt_holds_no_stage_or_commit_step"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Step 3 of the /code skill says the coder's prompt holds no stage or commit step, and that a commit the task asks for becomes the phase-end commit subject.

## Evidence

`test_code_skill_text.py` pins the sentence in the skill text. Rule meter, scenario CK01 (agent-evals 039e91ae), opus at the competing level, 8 runs per arm: rule on 8/8, rule off 1/8, +88 points.

A second sentence, that a coder's report of a denied git write is no STOP, was cut before ship. Scenario CK02 (run as CS02 at agent-evals e7fef959) scored it 8/8 on and 8/8 off: the fork already goes on to review without it. The cut and AC5's narrowing are in the plan's decision log.

## Result

Before, a fork copied the task's commit instruction into its coder's prompt, the git gate denied the coder's `git add`, and the fork stopped before review with nothing committed. Now the coder is not asked to commit.

## Watch

—

## Back-out

Remove the sentence from step 3 of the skill and the test that pins it.
