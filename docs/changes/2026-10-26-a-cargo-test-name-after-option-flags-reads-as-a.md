---
type: "Change"
change_type: "fixed"
title: "A cargo test name after option flags reads as a filtered run"
description: "A cargo test command is filtered when a bare name follows its options, or any token follows --, so a name that matches no test reads RED in the eng-spec dry run and the code-phase verification."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T10:33:09-05:00"}
seq: 57
kind: "fix"
components: ["script/criteria-dry-run", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_test_run_output.py::MatchesNoTestTest::test_a_cargo_test_name_after_option_flags_is_a_filter"
asked: ""
proof: []
unmeasured: ""
---

## Change

`test_run_output.py` decides a cargo test command is filtered with `cargo_test_is_filtered`. It reads the tokens after `cargo test`, skips options and the value of each option that takes one (`--test`, `--bin`, `-p`, `--features` and similar), and returns true at the first bare token or at any token after `--`. Before, only a name right after `cargo test` counted, so `cargo test --test billing totals` ran zero tests, exited 0 and read GREEN in the dry run and in the code-phase verification. `cargo test --test billing` with no name stays unfiltered.

## Evidence

judgment: a peer session found a plan with 6 checks reading GREEN for tests that were never written. The test fails on the base code for all four filtered commands and passes after; `test_a_cargo_test_with_only_options_is_not_a_filter` passes in both.

## Result

Tests in `parallel_tests.py` pass.

## Watch

—

## Back-out

Revert `cargo_test_is_filtered`, `CARGO_TEST`, `CARGO_VALUE_OPTIONS` and the `or` clause in `matches_no_test`, and the two new tests.

