---
type: "Change"
title: "Plan checks refuse a command that hands a shell its code"
description: "An eng-spec plan wrote an Automated Verification command as `sh -c '...'`. The plan check accepted it because `sh` is a program on PATH, and the shell hook then blocked the command when /code ran it. The check now treats a shell run with `-c` (sh, bash, zsh, dash, ksh, any flag cluster with c) as no verification command: the plan stops at write time with a message to write the command plainly or put the pipeline in an executable repo script. A shell that runs a script file still passes. The plan format says the same."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T07:16:10-05:00"}
seq: 174
kind: "fix"
components: ["script/code-step", "shared/plan-format", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_command_that_hands_a_shell_its_code_is_not_a_verification_command"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_boundary.py`: a new `hands_a_shell_its_code` check. It drops a leading `cd` and env assignments, then hands the words to `shell_command.shell_code_argument`, which also peels wrappers (`timeout`, `env`, `nice`, `uv run`, `docker exec`/`run`) and skips the values of `--rcfile`, `--init-file` and `-O`.
  - `verification_command` returns None for such a command, so the runner, the listed-commands gate and the criteria dry run never treat it as a check.
  - `verification_item_problem` names the reason: write the command plainly, or put the pipeline in an executable repo script.
  - The shape text that the write-time stop prints now says never to wrap a command in `sh -c` or `bash -c`.
- `_shared/plan-format.md`: the Automated Verification rule says the same, so `/eng-spec` writes plain commands.
- Tests that used `bash -c` as a stand-in check now use plain commands.
- No `/code` step runs evidence text as shell: `--evidence` is only stored. The shell-hook side of the item belongs to the bash-safety gate and is not changed here.
- Closes the toolkit side of the queue item eng-spec-verification-commands-and-queue-heredocs.

## Evidence

- A plan check accepted `sh -c '...'` as a verification command because `sh` is on PATH. The shell hook blocks that form, so the phase stalled at run time instead of at plan write time.
- The new test fails before the change: `verification_command` returned the `sh -c` span.

## Result

- The new and changed tests pass. A shell that runs a script file (`bash scripts/check.sh`) is still a verification command. ruff is clean.

## Watch

—

## Back-out

Revert the commit. Plans with `sh -c` checks then pass the write-time check again and stall when the hook blocks them.
