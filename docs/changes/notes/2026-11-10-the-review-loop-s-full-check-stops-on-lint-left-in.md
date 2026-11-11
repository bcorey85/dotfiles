---
type: "Change"
change_type: "fixed"
title: "The review loop's full check stops on lint left in any changed file"
description: "Before the review loop's full check and each recheck, it runs the repo's configured ruff, oxlint or eslint in check mode on every reviewed or touched file, test files included; lint left after one coder repair stops the loop as critical-blocker with the linter output."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T18:27:32-06:00"}
seq: 1
kind: "fix"
components: ["skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_format_files.py::LintProblemsTest::test_an_unfixable_violation_in_a_test_file_comes_back_with_the_linter_output"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/format_files.py` gains `lint_problems(repo, paths)`: the linters `run_formatters` picks, run only where the repo configures them, in check mode (`ruff check --force-exclude`, `oxlint`, or `eslint`, plus `--no-warn-ignored --max-warnings=0` only with a flat `eslint.config.*` config; a legacy `.eslintrc` repo gets neither, so an ignored file's warning is not a failure). A missing linter binary is no problem; a timeout is one. `review/full_check_gate.py` runs `lint_pass` at the start of `full_check_pass` and `recheck_full_check`: one `coder-lint` repair, then a `critical-blocker` stop naming every linter's output. The ruff formatter commands also get `--force-exclude`.

## Evidence

judgment: a review loop converged with ruff violations that have no autofix (RUF012, N802) left in changed test files, and pre-commit refused the commit. The loop's formatters ran `--fix` and ignored the exit code. The new tests fail before the change and pass after.

## Result

The loop's own full check on the final tree passed: 3358 tests in 126 files, 0 failed.

## Watch

—

## Back-out

Revert `lint_problems` in `lib/format_files.py`, `lint_pass` in `review/full_check_gate.py`, and their tests.
