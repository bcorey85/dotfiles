---
type: "Change"
title: "Toolkit script fixes: drop the dead hand-back gate, kill a timed-out coder check's process group, one plan-deviation format"
description: "A coder-gate check that times out now kills its whole process group and reports what it printed; the unregistered review-loop hand-back gate is gone; code_step and review_fix write plan-impact rulings in one format."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T19:17:35-05:00"}
seq: 12
kind: "fix"
components: ["script/coder-gate", "script/script-utils", "script/review-loop-gate", "script/plan-format", "script/code-step", "script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_coder_gate.py::RunCommandsTests::test_a_timeout_kills_a_child_that_holds_the_pipes_open"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `coder_gate.run_commands` runs each check through `script_utils.run_process`, which starts a new session and kills
  the process group on a timeout. `run_process` takes `env`. A failed or timed-out check reports stdout then stderr;
  before, a timeout reported no output and stderr was interleaved.
- `review_loop_gate.py` loses the PreToolUse `SubagentHandback` branch (`check_handback`, `last_handback_event`,
  `hand_back_insisted`, `reasons`, `HANDBACK_REFUSED`) and its test class. settings.json never registered it, so
  live runs never wrote its marks. The handoff check on a review-loop dispatch keeps one test.
- `plan_format.ruling_deviation` and `plan_format.ruling_owner` write every plan-impact ruling:
  `- <date> (Phase N): <decision>. Ruled by <owner> at <date time>.`, then the ruling and the disagreement. code_step
  and review_fix both call them, and review_fix appends through `plan_format.append_deviation`. review_fix drops its
  pipe format and its own section writer, leaves out the phase it does not know, and takes the owner from
  `git config user.name` as code_step does.
- `review_fix.git_output` was already fixed on the base branch.

## Evidence

The complexity review of code_step.py found the three defects outside its scope. A timed-out check whose shell
started a child that held the pipes kept that child alive.

## Result

The named test fails on the base script (no output reported on a timeout) and passes now. `bash tests/run.sh`:
2044 tests in 55 files, 0 failed; ruff clean; duplicate check clean.

## Watch

None. No intake number reads coder-gate timeouts or the deviation format.

## Back-out

Revert the commit.
