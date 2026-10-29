---
type: "Change"
change_type: "changed"
title: "code_step writes question.md on every stop on an agent's report or silence"
description: "Every /code stop on an agent's report or silence (no agent id, wait cap, coder stop, critical blocker, review cap, failed closing check) writes question.md with why, one line per open item and the exact command to go on; `skill-done fail` takes `--finding`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T23:05:53-05:00"}
seq: 85
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_a_coder_stop_on_its_report_writes_question_md_with_the_report_and_the_restart"
asked: ""
proof: []
unmeasured: "Free-text stops are not logged; no intake number reads them."
---

## Change

New `stop_with_question` in `code_step_core.py`, sharing `write_question` with `ask_user`, backs the launch-without-id,
wait-cap, coder-report and review-status stops. A failed closing check goes through `code_step_closing.py`: `skill-done
fail` takes optional `--finding "<one line>"` and falls back to the open Success Criteria. Still without question.md: the
review-not-converged and skill-done verdict stops in the boundary module, and script-run verification stops.

## Evidence

Two runs stopped with a free-text report and no question.md: a coder that could not run an evidence phase, and a
verify phase whose doc-only findings the fork could not apply.

## Result

Those stops hand back a question with each blocker and the next command.

## Watch

None.

## Back-out

Revert the commit.
