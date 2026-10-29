---
type: "Change"
title: "check_scope reads a scoped cargo, go, rspec or phpunit run as targeted, so the full check refuses it"
description: "lib/check_scope reads a cargo, go, tsc, mypy, pyright, bats, rspec, phpunit or dotnet run that names a file, a directory, a package or a test, or sets a selector flag, as targeted; full_check.py refuses it as a scoped command, and a whole run stays none for the coder gate."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T00:00:00-05:00"}
seq: 265
kind: "fix"
components: ["script/full-check", "script/check-scope"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_runner_that_check_scope_reads_by_its_flags_is_not_run_on_named_files_or_tests"
asked: ""
proof: []
unmeasured: ""
---

## Change

`full_check.py` refused only a command that `lib/check_scope` reads as targeted. `check_scope` did not read cargo, go, bats, rspec, phpunit, tsc, mypy, pyright or dotnet, so `cargo test tests/foo.rs` or `go test -run TestX ./...` ran and could print `passed`, and the stop gate counted it as a full check.

`check_scope` now reads those runners, so every caller and every make recipe gets the reading. A run is targeted when it has a positional word after the runner and its subcommand (a file, a directory, a package such as `go test ./pkg/...`, or a bare test name such as `cargo test empty_input`), or a selector flag in its space or `=` form: cargo `-p`/`--package`, `--test`, `--bench`, `--bin`, `--example`, `--lib`, `--doc`, `--bins`, `--tests`, `--benches`, `--examples`, nextest's `-E`, `--filterset`, `--filter-expr`, `--skip` and `--partition`, and libtest's `--ignored` switch; go `-run`, `-skip` and `-fuzz`; mypy `-p`/`--package`, `-m`/`--module`; dotnet `--filter`; rspec `-e`/`--example`, `-t`/`--tag`, `-P`/`--pattern`, `--only-failures` and `--next-failure`; phpunit `--filter`, `--testsuite` and `--group`; bats `--filter`, `-f` and `--filter-tags`. A `+toolchain` word, `./...` and the value of a value flag each runner lists (`tsc -p`, `dotnet --project`, `cargo --target-dir`, `go -coverprofile`) are not a scope. Bare `cargo nextest run` is a whole run, and so is `--run-ignored all` or `default`; `--run-ignored only` is targeted. bats' `-p` is `--pretty`, a switch, so it scopes nothing.

A whole run of these runners stays `none`, not `whole`, so the coder gate, which refuses only `whole`, lets coders run `cargo test --workspace` as before. The CLAUDE.md `Quality check:` command and a `Full suite: CI` repo keep their exceptions.

The value-flag lists are kept by hand and stay incomplete. The gap fails safe: a value flag missing from a list reads its value as a scope word, so the full check refuses that whole run out loud with `not run (scoped command ...)` and never lets a scoped run pass as full. The fix is to add the flag to its runner's list.

## Evidence

Failing first: on master the new tests in `test_full_check.py` and `test_coder_gate.py` fail.

## Result

The new tests pass. Scoped modules pass; ruff is clean.

## Watch

—

## Back-out

Revert the commit.
