---
type: "Change"
title: "A hand-back gate timeout is reported as a timeout, not a failing suite"
description: "coder_gate.py records a command that hits its timeout apart from failures, lets the hand-back through stamped with the timeout and no test result, and code_step reports it as timed out; a new test covers the listed cargo commands on the --phase start path."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T18:29:14-05:00"}
seq: 67
kind: "fix"
components: ["script/coder-gate", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_the_hook_allows_a_gate_whose_only_command_timed_out_and_stamps_the_timeout"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A gate command that hits the 1200 s timeout goes into its own `timed_out` list, never into the failures.
- A timeout alone does not deny the hand-back: the run's result is `timeout`, and the hand-back is stamped with each
  timed-out command, the last 600 characters of its output, and that the gate got no result from it (the command is too
  broad, or a test hangs). A real failure in the same run still denies.
- code_step reads a hand-back only up to the gate stamp, so command output in a timeout tail never becomes a coder
  flag, a plan-impact finding or an exception.
- The `clear` printout, the gate log row and code_step's tests-run text name timed-out commands as timed out.
- A test starts a phase with `--phase 1` and checks the gate takes the cargo commands the phase lists in place of the
  crate-wide `cargo test --tests` and clippy.

## Evidence

- A Rust phase's gate ran a crate-wide `cargo test --tests`, timed out twice at 1200 s, and the review loop asked the
  user which test failed. No test had failed, so the question had no answer.
- The new tests fail on the base commit and pass after.

## Result

- Full suite and ruff pass on the worktree.

## Watch

—

## Back-out

Revert the commit.
