---
type: "Change"
change_type: "fixed"
title: "Command classification has one owner and one pass judgement"
description: "lib/check_scope.py owns every command question (runs_tests, runner_family, is_check, whole or targeted, test filter, cargo test target) and check_output.check_verdict is the one rule for whether a finished check passed, failed, failed with exit 0, ran no tests or did not run. The command tables of test_run_output, code_step_gates, code_step_verification and quality_check_cap are deleted and their callers import the owner. Where an old table and the owner disagreed, the owner answers strictest, except the looser answers marked Looser in the note (matches_no_test reads a redirect word and a selector flag's value as no filter; runs_tests reads a `test` word after a package verb as no test run; criteria_verdict reads a filtered run that matched no test as green when prints_own_runner_summary is False for the command, such as `echo pytest -k nothing` or `! cargo test x`)."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T02:55:46-05:00"}
seq: 317
kind: "fix"
components: ["script/check-output", "script/full-check", "script/coder-gate", "script/criteria-verdict", "script/check-scope", "script/test-run-output", "script/quality-check-cap", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_check_output.py::CheckVerdictTest::test_check_verdict_and_every_pass_rule_agree_on_each_command_and_output"
asked: ""
proof: []
unmeasured: "The change moves no intake number: it makes the deciders answer the same input the same way, which only the table tests read."
---

## Change

Pass judgement. `lib/check_output.py` gains `check_verdict(command, code, output)`, returning `passed`, `failed`
(non-zero exit), `failed-exit-zero` (exit 0 while a runner summary reports failures), `ran-no-tests` (exit 0 from a
filtered run that matched no test, or a test command whose output says `Ran 0 tests` / no tests ran) or `not-run`
(code None, a timeout). `SUMMARY_FAILURE` moved there from `review/full_check.py`; the Django-only
`DJANGO_TEST_COMMAND` and `DJANGO_RAN_NO_TESTS` in `code/coder_gate.py` are deleted (the existing `NO_TESTS_RAN_OUTPUT`
and `test_run_output.matches_no_test` are reused). `full_check.run`, `coder_gate.run_commands` and
`criteria_verdict.judge_item` map the verdict to their own result names and keep their own CI-only, UNVERIFIED,
setup-fault and search-ban handling.

Command classification. `lib/check_scope.py` owns every command question: `runs_tests`, `names_test_runner`,
`prints_own_runner_summary`, `runner_family`, `is_check`, `names_test_filter`, `names_cargo_test_target`, plus the
existing `command_check_scope` and `runs_whole_check`. `check_scope.RUNNER_VALUE_FLAGS` and
`RUNNER_SELECTOR_VALUE_FLAGS` hold the cargo value flags for the filter answer; `CARGO_CRATE_VALUE_FLAGS` repeats three
of them for the cargo target answer. `test_run_output` keeps output reading (`runner_summaries`, `passed_test_count`, `matches_no_test`) and imports
the command questions from `check_scope`; `check_output` and `code_step_review_stops` import them from `check_scope`.

Tables and functions deleted from their old homes:

- `lib/test_run_output.py`: `TEST_RUNNER`, `TEST_RUNNER_WORDS`, `TEST_FILTER`, `TEST_WORD`, `SCRIPT_RUNNERS`, `NON_TEST_PROGRAMS`,
  `runs_tests` and `prints_own_runner_summary` (moved to `check_scope`); `CARGO_TEST`, `CARGO_VALUE_OPTIONS` and
  `cargo_test_is_filtered` (replaced by `check_scope.names_test_filter`).
- `code/code_step_gates.py`: `TEST_FAMILY_PATTERNS` (moved to `check_scope.RUNNER_FAMILY_PATTERNS`, read through
  `runner_family`).
- `code/code_step_verification.py`: `WHOLE_SUITE` (replaced by `full_check.is_configured_check`).
- `gates/quality_check_cap.py`: `CHECKS`, `CHECK_START`, `CARGO_TEST`, `CARGO_TARGET_FLAGS`, `CARGO_WHOLE_TREE_FLAGS`,
  `CARGO_VALUE_FLAGS` and `is_scoped_cargo_test` (replaced by `is_check` and `names_cargo_test_target`).

Pass-judgement inputs whose answer changed (two kinds of input got looser: the first item below and the Looser item after the `cat run.log` item, which covers any command `prints_own_runner_summary` reads False, such as `echo pytest -k nothing` and `! cargo test x`):

- `coder_gate`: exit 0 with `Ran 0 tests` from a command that names `manage.py test` but is no test command (for
  example `echo manage.py test; echo "Ran 0 tests"` or `bash -c "python manage.py test"`) was a setup fault, now a pass.
- `coder_gate`: exit 0 whose runner summary reports failures (for example `Tests  1 failed | 2 passed`) was a pass, now
  a failed command.
- `coder_gate`: exit 0 from a filtered test run that matched no test was a pass, now a failed
  command.
- `coder_gate`: exit 0 with `Ran 0 tests` or `no tests ran` output from a test command, other than that
  `manage.py test` case, was a pass, now a setup fault, which does not deny.
- `criteria_verdict`: exit 0 whose runner summary reports failures was GREEN, now RED with a note.
- `criteria_verdict`: exit 0 with `Ran 0 tests` or `no tests ran` output from a test command (Django and unittest runs, which
  `matches_no_test` never judged) was GREEN, now RED with the no-test-matched flag.
- `full_check`: exit 0 from a test command whose output says `Ran 0 tests` or no tests ran, or a filtered run that matched
  no test, was `passed` when another summary line was present, now `unverified (exit 0, no test result shown)` (or the CI-only result in a CI repo).
  A filtered command is normally refused by scope before it runs, so this reaches only a declared check.
- `coder_gate` and `criteria_verdict`: exit 0 from `cat run.log`, `tail -n 50 run.log` or a `!`-negated
  runner holding a failing summary (`1 failed, 2 passed`) was a pass, now a failed command (failed-exit-zero).
  One case was not a pass: `criteria_verdict` on a filtered negated run with no passed test (`! pytest t.py::test_new`
  printing `1 failed`) was already RED; it stays RED, now with the summary-failure note and no no-test-matched flag.
  Every command that exits 0 and prints a failed runner summary fails, whatever its programs. Only the
  no-test-matched answer is still limited to a command with a step that can print its own summary
  (`prints_own_runner_summary`).
- Looser: `criteria_verdict` for the no-test-matched check, on any command `prints_own_runner_summary` reads False
  (every step a search, a print or negated), went from RED to GREEN. Two examples: `echo pytest -k nothing` with no
  passed test and `! cargo test x`.
- `NON_TEST_PROGRAMS` lists only some of the programs that cannot print a runner summary; that is a known gap, and this
  change does no list work.
- `coder_gate`, `criteria_verdict` and `full_check`: exit 0 from `bash tests/run.sh` holding `1 failed, 2 passed`
  is a failed command (failed-exit-zero), the wrapper having swallowed the runner's exit code.

Command-classification answers that changed (the owner gave the strictest answer wherever an old table and it
disagreed; no caller got looser except the items marked Looser):

- `quality_check_cap` now counts as a check, so a repeat is capped (was not a check): `python -m pytest`, `uv|poetry|pipenv
  run pytest` and any command a wrapper peels to a check, `docker exec c pytest`, a program named by path
  (`./node_modules/.bin/jest`), script variants (`npm run test:unit`, `yarn lint:fix`, `pnpm build:prod`),
  `manage.py test`, `cargo nextest run` (whole or on a name), `cargo +nightly clippy|check`, and `pyright` and `bats`,
  bare or on a name. A path form such as `./vendor/bin/phpunit` is the only new `phpunit` case. `cargo +nightly test
  <name>` was not a check and is now a check that names a target, so it stays uncapped.
- `quality_check_cap` also caps every command that gives a script runner a test word, and every step that names a
  runner word anywhere (`rm -rf jest`, `python tools/x.py pytest`), which `is_check` now includes: `mocha`,
  `npx mocha`, `make test-unit`, `make -C x test`, `just test`, `deno test`, `pnpm --filter api test`. A `PACKAGE_MANAGERS` step with a verb of
  `PACKAGE_VERBS_AND_LOOKUPS`, a `LOOKUP_PROGRAMS` step, or `command -v` is no check: `npm install test-x`, `pip install pytest`,
  `python -m pip install pytest`, `which pytest`, `command -v pytest`. A `pacman` step that names a runner stays a
  check: `pacman -S pytest`. The verb is the first word after the program, so `npm test list` is a check.
- `quality_check_cap` target answer for `cargo test`: `cargo test --retries 2`, `--test-threads 4`, `-A x`, `-P ci` and `--format x` were named targets and
  uncapped; they now read as full runs and are capped (stricter), as does every other `RUNNER_VALUE_FLAGS["cargo"]`
  flag the old `CARGO_VALUE_FLAGS` lacked (`-D`, `-W`, `--failure-output`, `--success-output`, `--status-level`,
  `--final-status-level`, `--max-fail`, `--cargo-profile`, `--archive-file`, `--logfile`, `--run-ignored all`, `--run-ignored default`;
  `ignored-only` and `--run-ignored only` / `--run-ignored=only` stay named targets, `NEXTEST_IGNORED_ONLY_VALUES`).
  Otherwise unchanged: `--lib`, `--doc`, `--test|--bin|--example|--bench`
  or a test name is a named target; `-p`, `--package`, `--exclude`, `--tests`, `--bins`, `--benches`, `--examples`,
  `--ignored`, a workspace or `--all-targets` flag, and words after `--` stay a full run. `command_check_scope` still
  reads `cargo test -p core` as targeted for the coder gate and the full check, so `names_cargo_test_target` is the
  separate, stricter answer for the repeat cap.
- `code_step_verification` skips only a command that matches the repo's configured `Quality check:` command
  (`full_check.is_configured_check`); the review loop runs that one. Every other phase command runs, such as
  `npm run test:e2e`, `pytest -q` and `npm test && git diff`. A repo with no `Quality check:` line skips nothing.
- `matches_no_test` now reads `--skip` as a test filter: `cargo nextest run --skip x` and `npm test -- --skip x`
  read as filtered.
- `matches_no_test` now reads script runners as test runs, so a filtered exit-0 run with no passed test is flagged:
  `make test -k x`, `just test -k x`, `deno test --filter x`, `python manage.py test -k x`, `cargo +nightly test x`.
- Looser: `matches_no_test` no longer reads as a filter the value after one of five cargo flags that
  `RUNNER_VALUE_FLAGS` knows and the old option list did not: `-A`, `-W`, `-D`, `--retries` and `--test-threads`
  (`cargo test -A warnings`, `cargo test --retries 2`). A test row pins each flag.
- Looser: `matches_no_test` no longer reads `cargo test x` that sits only in quoted text of another step
  (`echo "cargo test x"`). `runs_tests`, `is_check` and `names_test_filter` are false and the scope is `none`.
  A test pins it.
- Looser: `names_test_filter` and `matches_no_test` no longer read a redirect word or a selector flag's value as a
  filter: `cargo test 2>&1`, `cargo test > log`, `cargo test --lib 2>&1` and `cargo test -E x` went from True to
  False, and `matches_no_test("cargo test 2>&1", 0, "test result: ok. 0 passed; 0 failed")` is now False.
- Looser: `runs_tests`, and so `takes_listed_test_command`, `check_output.runs_tests` and `check_verdict`, no longer
  read a `test` word after a package-manager verb in `PACKAGE_VERBS` as a test run: `npm install test-x`,
  `npm i test-utils` and `pnpm --filter api add test-x` went from True to False. A runner word stays a test run for
  `runs_tests` (`npm install -D jest`, `pip install pytest`, `pnpm --filter api add jest`). A flag's value is no verb.
- Unchanged: `test_command_families` (same patterns).

## Evidence

Judgment: the three pass rules decided the same exit-0 outputs differently (the architect read of 2026-10-29 listed
`full_check.py` around 369, `coder_gate.py` 259-264 and `criteria_verdict.py` 118), and about eight command tables
disagreed on whether a command runs tests, is a check or is whole.

## Result

The pass table test runs nineteen (command, code, output) rows through `check_verdict` and each of the three callers
and gets one answer per row; the plain-failure row skips only the exact `full_check` result compare; the timeout row
carries a `full_check` result and skips `criteria_verdict`. The command table test
(`tests/scripts/test_check_output.py::CommandClassificationTest::test_each_command_gets_one_answer_from_check_scope_and_every_former_decider_agrees`)
runs twenty-four commands through `check_scope` and every former decider and gets one answer per command. Its neighbours
pin `is_check`, the filter answer and the cargo target answer, and `test_quality_check_cap.py` pins the cap. Test files
for the touched modules pass.

## Watch

None: see `unmeasured`.

## Back-out

Revert `check_verdict` and its call sites; restore `SUMMARY_FAILURE` in `review/full_check.py`, and
`DJANGO_TEST_COMMAND` and `DJANGO_RAN_NO_TESTS` in `code/coder_gate.py`. Restore the deleted command tables in
`lib/test_run_output.py`, `code/code_step_gates.py`, `code/code_step_verification.py` and `gates/quality_check_cap.py`,
and remove the command questions added to `lib/check_scope.py`.
