---
type: "Change"
title: "code-step runs scoped Rust tests and refuses checks that never end"
description: "For a Rust phase, the hand-back check runs only the test targets that hold the changed files (the lib, a bin or one test file), not every target in the workspace. A verification item that never ends (`tail -f`, `watch`, `sleep`, an editor, `claude`) or a bare word that is not a program is refused when the plan is written. A plan can mark an item CI-verified or human-only, and code-step does not run it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T14:43:56-05:00"}
seq: 4
kind: "behavior"
components: ["script/code-step", "script/plan-format", "shared/plan-format"]
evidence: ["work incident", "tests"]
watches: ["rust-code-step-seconds"]
---

## Change

- **Scoped Rust tests:** for each changed file in a crate, the hand-back check runs the whole target that holds it:
  - `cargo test --lib --bins` for any `src/` file of a crate with `src/lib.rs`, and `--bins` for a crate with no library;
  - `--bin <name>` for a file under `src/bin/<name>`;
  - `--test <name>` for `tests/<name>.rs`, or for a file under a `tests/<name>/` dir that holds a `main.rs`;
  - `--tests` for a shared helper dir under `tests/`, such as `tests/common/`.

  There is no module filter. A module filter missed a lib test in an unchanged module that pinned the old behavior, and compiling the test binary costs more than running all of its tests. A `src/` change does not run the integration tests in `tests/`, because CI runs the full suite. code-step never emits a bare `cargo test`.
- **Checks that never end:** an item that starts with `claude`, `yes`, `watch`, `top`, `htop`, `less`, `more`, an editor or `sleep`, or runs `tail -f`, `-F` or `--follow` in any flag group, is not a check. A bare program name with no argument is not a check. A repo file counts as a program only when the item names a path with `/`.
- **Third item shape:** `**CI-verified**:` and `Human-only:` items are listed in the done line as not run here. One function decides "runs no command" for the plan check, the gate variables and the verification run.
- **Plan format:** the shared plan rules name the three item shapes and the ban on commands that never end.
- **Records:** a deviation record writes the ruling in one line, and a sign-off line names who and when, with no quote of the user.

## Evidence

Work incident: agent-ledger sessions reported Rust phases that ran the whole crate test suite at each hand-back, on a machine whose CPU sits at 100%. Tests: the lane suites pass (code_step 428, script_utils 99, plan_format 79, review_fix 115, coder_gate 7). A seeded mutant pass caught 101 of 101 mutants. Six review passes. Scratch crates confirmed that each target rule runs the failing test it must catch: a lib test, a `main.rs` unit test, and an integration test that uses a shared helper. The last pass found no defect, only two clean-ups that change no behavior.

## Result

Ready to install. The verify_branch real-plan test fails on plans in the LED-16 and LED-25 worktrees, with the installed scripts too. This change does not cause it.

## Watch

None. No intake metric times the hand-back check or counts phases stopped on an unreadable item. Unmeasured behavior change.

## Back-out

Restore `code-step.py`, `plan_format.py`, `script_utils.py`, `verify-prep`, `review-fix.py` and their tests from the dotfiles history, and drop the item-shape rule from `skills/_shared/plan-format.md`.
