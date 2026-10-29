---
type: "Change"
change_type: "fixed"
title: "A resumed /code run reaches the right next step"
description: "Five code-step defects that sent a stopped or resumed /code run to the wrong step: a resumed coder at the wait cap, `start after-review` over an open run, a phase given inside task text, a plan-edit coder at the cap, and a review-loop hand-back from an agent the run did not launch."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T00:02:50-05:00"}
seq: 1
kind: "fix"
components: ["script/code-step"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest.test_a_resumed_coder_that_reaches_the_cap_again_keeps_the_resume_text_and_has_no_stop_reason"
unmeasured: ""
---

## Change

- **A resumed coder at the wait cap** keeps the resume text and gets no stop reason. Before, the second cap stopped the run as if the coder had never handed back.
- **`start` with a verb name as its first word** is refused before the open-run check. So `start after-review` over an open run names `resume`, and does not offer to drop the run.
- **A plan or `--phase` inside task text** is refused with the parsed `start` command. Before, a bare `--phase` with no plan went through as task text.
- **A plan-edit coder at the cap** stops with reason `coder-cap` and text only. It says that only the phase coder resumes, and that `start --restart` dispatches it again.
- **A review-loop hand-back counts only from the agent id of the review's launch.** A hand-back from any other agent is logged and ignored. A review resumed with SendMessage keeps its launch id, so it still matches.

## Evidence

Tests: each defect has a test in `test_code_step_resume.py` that fails on the installed script and passes on this one. The other suites pass: test_code_step_resume 51, termination 1, test_fixes 13 (2 expected failures). test_code_step passes 427 of 429. The other 2 are timing-cap tests that fail under load 27 and pass alone.

## Result

Built in a lane bundle. The review approved it after five fix rounds. Installs with the resume verb change.

## Watch

None. A fix: the tests prove it.

## Back-out

Restore `code-step.py` and its tests from the dotfiles history.
