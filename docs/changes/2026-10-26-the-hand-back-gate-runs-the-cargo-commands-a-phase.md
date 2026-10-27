---
type: "Change"
title: "The hand-back gate runs the cargo commands a phase lists"
description: "When a plan phase lists cargo commands under Automated Verification, code_step.py start sets the hand-back gate to those commands in place of crate-wide clippy and the cargo test commands it derives from the phase's files."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T09:18:01-05:00"}
seq: 48
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_gate_takes_the_cargo_commands_the_phase_lists_in_place_of_the_derived_ones"
asked: ""
proof: []
unmeasured: ""
---

## Change

`derive_gate_commands` in `code_step.py` reads the phase's Automated Verification commands the way the phase boundary reads them. When any of them runs cargo, the hand-back gate takes those cargo commands as written and skips `cargo_commands`. Before, the gate always added crate-wide `cargo clippy --all-targets` and widened to `cargo test --tests` (every test target in the crate) when a changed file was a shared helper under `tests/<dir>/`, whatever the plan listed. The gate runs at every coder hand-back. A phase that lists no cargo command keeps the derived commands. The npm and Python derivations do not change.

A phase that lists only cargo test commands now gets no clippy in the gate. The plan's own commands are the contract for that phase.

## Evidence

judgment: a Rust repo whose rules ask coders to run only the tests for the files they changed reported that each hand-back ran the crate's full suite, and one coder hit the quality-check time cap. `test_gate_takes_the_cargo_commands_the_phase_lists_in_place_of_the_derived_ones` fails on the base commit (the gate holds clippy and `cargo test --tests`, not the listed command) and passes after. `test_gate_keeps_the_derived_cargo_commands_when_the_phase_lists_no_cargo_command` passes in both.

## Result

Full suite and ruff pass.

## Watch

—

## Back-out

Revert `listed_cargo_commands`, `RUNS_CARGO` and the `listed_cargo or` branch in `derive_gate_commands`, and the two tests and their helper in `test_code_step.py`.
