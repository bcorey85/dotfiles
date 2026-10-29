---
type: "Change"
change_type: "fixed"
title: "check_scope reads a run that excludes part of the suite as targeted"
description: "lib/check_scope reads a test or lint run that leaves files, packages, groups or tags out (cargo --exclude, mypy --exclude, rspec --exclude-pattern, phpunit --exclude-group, bats --negative-filter, manage.py --exclude-tag, pytest --ignore and the like) as targeted, so full_check.py refuses it and the stop gate never counts it as a full check."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T15:36:18-05:00"}
seq: 276
kind: "fix"
components: ["script/full-check", "script/check-scope"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_coder_gate.py::CommandCheckScopeTests::test_a_run_that_excludes_part_of_the_suite_is_targeted"
asked: ""
proof: []
unmeasured: ""
---

## Change

`check_scope` read a run that leaves part of the suite out as a whole run. `cargo test --workspace --exclude foo`, `mypy --exclude tests .`, `phpunit --exclude-group slow` and `pytest --ignore=tests/slow` could pass `full_check.py` and count as a full check.

Each runner's exclude flags now pick part of the suite, in their space and `=` forms:

- cargo and nextest `--exclude`; mypy `--exclude`; rspec `--exclude-pattern`; phpunit `--exclude-group`, `--exclude-filter` and `--exclude-testsuite`; bats `--negative-filter`. Cargo, mypy, rspec and phpunit `--exclude-group` moved from the per-runner value flags to the per-runner selector flags; bats `--negative-filter`, phpunit `--exclude-filter` and `--exclude-testsuite` are added there.
- `manage.py test --exclude-tag`, in both forms; the flag stays a value option so a derived gate command keeps its value word.
- For the runners matched by command prefix, the `=` form of each runner's own leave-out flags, kept per runner: pytest `--ignore`, `--ignore-glob` and `--deselect`; vitest `--exclude`; jest `--testPathIgnorePatterns`; eslint `--ignore-pattern` and `--ignore-path`; ruff `--exclude` and `--extend-exclude`. ruff `--ignore` takes rule codes, so `ruff check --ignore=E501 .` stays a whole run. An npm, yarn, pnpm or bun script reads the flags of every runner but ruff. Their space form already read its value as a scope word.

A targeted run is still allowed for coders; only the full check and the stop gate treat it differently.

## Evidence

Failing first: of the 23 cases in the new test other than the two added later, on the base 11 read as a whole run, 11 read none, and 1 (`phpunit --exclude-testsuite unit`) already read targeted. All 23 now read targeted. Two more cases were added after that measurement (`npx eslint --ignore-path=.eslintignore .` and `phpunit --exclude-testsuite=unit`) and were not measured on the base.

## Result

The new tests pass. The full suite passes (3582 tests, 0 failed); ruff is clean.

## Watch

—

## Back-out

Revert the commit.
