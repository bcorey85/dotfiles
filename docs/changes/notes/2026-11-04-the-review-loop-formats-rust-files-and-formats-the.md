---
type: "Change"
change_type: "fixed"
title: "The review loop formats Rust files and formats the reviewed files before its full check"
description: "format_files runs rustfmt on .rs files in a repo whose check command runs cargo fmt or rustfmt (or that holds a rustfmt.toml), with each crate's edition, and the scripted review loop formats the reviewed and touched files before its full check, so a later format pass changes nothing and the reviewed tree stays the committed tree."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T23:55:57-06:00"}
seq: 8
kind: "fix"
components: ["script/format-files", "script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_converged_loop_formats_the_reviewed_files_before_its_full_check_so_a_later_format_changes_nothing"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/format_files.py` gains `RUST_SUFFIX`, `RUSTFMT_COMMANDS`, `RUSTFMT_CONFIG_FILES`, `DEFAULT_RUST_EDITION`, `repo_formats_with_rustfmt`, `manifest_edition`, `rust_edition` and `run_rust_formatters`. `run_formatters` collects `.rs` paths and runs `rustfmt --edition E <files>` once per edition, the edition read from the nearest `[package]` or inherited `[workspace.package]`. `review_loop_script.py` gains `LoopRun.format_reviewed_files`, which `walk` calls before `full_check_pass`. A spec tick under `docs/` is already a notes path the fingerprint leaves out. A comment trim after convergence still needs a review: no script proves it trivial.

## Evidence

judgment: two sessions reported a `cargo fmt`-only critical blocker that the loop could not fix, and a `cargo fmt` after convergence that moved the tree off the reviewed fingerprint and denied the commit. `test_format_files.py::RunFormattersTest::test_the_loop_path_formats_rust_files_in_a_repo_whose_check_runs_cargo_fmt` and `::test_rust_files_take_the_edition_their_crate_inherits_from_the_workspace` fail on the base commit and pass after, as does the loop test named above. A real edition-2024 crate formatted by the new path passed `cargo fmt --check`.

## Result

`test_format_files.py` 11 of 11, `test_format_changed.py` 36 of 36 and `test_review_loop_script.py` 222 of 222 pass; lint clean.

## Watch

—

## Back-out

Revert the Rust functions and constants in `format_files.py`, `format_reviewed_files` and its call in `review_loop_script.py`, and the tests.
