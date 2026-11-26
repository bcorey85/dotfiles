---
type: "Change"
change_type: "fixed"
title: "A coder's denied git write no longer stops the code run"
description: "The /code skill keeps stage and commit steps out of a coder's prompt and treats a coder's report of a denied git write as no stop, so the run goes on to review with the changes uncommitted."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T18:33:00-06:00"}
seq: 6
kind: "fix"
components: ["skill/code"]
evidence: ["tests/scripts/test_code_skill_text.py"]
watches: []
test: "tests/scripts/test_code_skill_text.py::CodeSkillTextTest.test_a_coder_prompt_holds_no_commit_and_a_denied_git_write_does_not_stop_the_run"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Step 3 of the /code skill says the coder's prompt holds no stage or commit step, and that a commit the task asks for becomes the phase-end commit subject. It also says a coder's report of a denied git write is no STOP: the run goes on to step 4 with the changes uncommitted.

## Evidence

`test_code_skill_text.py` pins both sentences in the skill text. The test failed before the edit and passes after.

## Result

Before, a fork copied the task's commit instruction into its coder's prompt, the git gate denied the coder's `git add`, and the fork stopped before review with nothing committed. Now the coder is never asked to commit and a denied write does not end the run.

## Watch

—

## Back-out

Remove the two sentences from step 3 of the skill and the test that pins them.
