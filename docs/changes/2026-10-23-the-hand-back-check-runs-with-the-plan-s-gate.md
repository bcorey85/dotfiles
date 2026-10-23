---
type: "Change"
title: "The hand-back check runs with the plan's gate variables"
description: "code-step reads the `NAME=value` words that the plan's verification commands start with, plus the repo's gate variables, and stores them in the gate with `coder-gate.py set --env`. The hand-back hook runs every check with them, so it sees the same settings as the coder's own run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T14:43:56-05:00"}
seq: 5
kind: "fix"
components: ["script/coder-gate", "script/code-step"]
evidence: ["judgment", "tests"]
watches: []
---

## Change

- `coder-gate.py set --env NAME=value` stores the variables in the gate file. `run_commands` runs each command with the process environment plus those variables. A gate file written before this change has no variables and still runs.
- `set` refuses an `--env` with no value.
- A value with `$`, `~` or a shell character is not a fixed setting, so the gate never stores a value that the shell would expand in a different way.

## Evidence

Judgment: a code review of the scoped-tests change found that the dispatch prompts tell the coder to put the plan's variables before each command, but the hand-back gate ran the commands without them. A plan that sets an oracle path for its tests then passes for the coder and fails at the gate. Tests: `test_coder_gate.py` (7) covers the stored variables, an old gate file, and the stray `--env`. The reproducing test is `test_set_refuses_a_trailing_env_flag_with_no_value` for the refusal and the env round-trip test for the fix.

## Result

Not installed yet. It ships in the same install as the scoped Rust tests change.

## Watch

None. A fix: tests prove it.

## Back-out

Restore `coder-gate.py` from the dotfiles history and delete `tests/scripts/test_coder_gate.py`. Old gate files keep working either way.
