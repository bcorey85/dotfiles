---
type: "Change"
change_type: "fixed"
title: "a Rust phase that lists its cargo commands also runs clippy on the targets it changed"
description: "A lint in a changed Rust file is caught by the phase gate in about a minute instead of by a 20-minute full gate, when the plan lists its own cargo commands because the repo bans the crate-wide clippy run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T05:01:19-05:00"}
seq: 324
kind: "fix"
components: ["script/code-step", "script/check-scope"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_phase_that_lists_its_cargo_tests_gets_clippy_on_the_test_target_it_changed"
asked: ""
proof: []
unmeasured: ""
---

## Change

- When a phase lists cargo commands and none of them runs clippy, the phase gate adds one clippy per crate, scoped to
  the targets of the files the phase names, with `-D warnings`. It runs before the listed commands. Before, the
  listed commands replaced the derived ones and no clippy ran. The scopes:
  - `--test NAME` for a test file, `--tests` for a shared test helper.
  - `--example NAME` / `--bench NAME` for a file under `examples/` / `benches/`, and `--examples` / `--benches` for
    a helper directory without a main.rs.
  - `--bin NAME --tests` for a binary, and `--lib --bins --tests` (or `--bins --tests`) for any other `src/` file, a
    manifest or a file outside those folders. `--tests` lints the `#[cfg(test)]` modules, which a plain
    `--lib --bins` run skips.
- A phase that lists no cargo command keeps `cargo clippy --all-targets -- -D warnings` as before. A phase that lists
  its own clippy gets no derived one.
- `check_scope.runs_cargo_clippy` says whether a command runs `cargo clippy` once its wrappers are peeled. A quoted
  "cargo clippy" inside another command does not count.
- `target_directory_scope` holds the one rule for a file under `tests/`, `examples/` or `benches/`: its own target
  when it is `<folder>/<name>.rs` or in a folder with a main.rs, every target of the kind otherwise.

## Evidence

judgment: on two branches in one day, a lint in a changed test file (needless_borrow, type_complexity) cost one
20-minute full gate run each to find. The repo bans the crate-wide local clippy run, so the plan listed its own
cargo commands and the phase gate ran no clippy.

## Result

The named test fails before (the gate holds only `cargo test --test orders`) and passes after.
`test_a_quoted_cargo_clippy_inside_a_listed_command_is_no_clippy_run` and the two `test_runs_cargo_clippy_*` tests
cover the quoted case, wrappers and global flags.
`test_scoped_clippy_lints_each_named_target_of_a_crate_once_and_a_manifest_as_library_and_binaries`,
`test_scoped_clippy_lints_a_lone_binary_source_file_with_the_test_targets` and
`test_scoped_clippy_lints_a_build_script_as_library_binaries_and_tests` cover the target merge and the unit-test
modules. The three `test_scoped_clippy_lints_*example*` tests cover the example and bench targets.

## Watch

None.

## Back-out

In `code_step_gates.py`, delete `scoped_clippy_commands`, `example_or_bench_scope`, `TEST_TARGET_FLAGS` and
`CARGO_TARGET_FLAG` (keep `crate_unit_scope`, `crate_of_rust_path` and `target_directory_scope`), and have
`derive_gate_commands` take `listed_cargo or cargo_commands(...)` again. Delete `runs_cargo_clippy` in
`check_scope.py` with its `resolved_command_words` import, and the tests.
