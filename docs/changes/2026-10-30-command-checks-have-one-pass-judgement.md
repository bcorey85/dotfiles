---
type: "Change"
change_type: "fixed"
title: "Command checks have one pass judgement"
description: "check_output.check_verdict(command, code, output) is the one rule for whether a finished check command passed, failed, failed with exit 0, ran no tests or did not run; full_check, coder_gate and criteria_verdict call it instead of each deciding alone. For output of `Ran 0 tests`, coder_gate gives a non-denying setup fault, and for a filtered run that matched no test it denies; full_check gives unverified, and criteria_verdict gives RED."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T02:55:46-05:00"}
seq: 317
kind: "fix"
components: ["script/check-output", "script/full-check", "script/coder-gate", "script/criteria-verdict"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_check_output.py::CheckVerdictTest::test_check_verdict_and_every_pass_rule_agree_on_each_command_and_output"
asked: ""
proof: []
unmeasured: "The change moves no intake number: it makes three pass rules answer the same input the same way, which only the table test reads."
---

## Change

`lib/check_output.py` gains `check_verdict(command, code, output)`, returning `passed`, `failed` (non-zero exit),
`failed-exit-zero` (exit 0 while a runner summary reports failures), `ran-no-tests` (exit 0 from a filtered run that
matched no test, or a test command whose output says `Ran 0 tests` / no tests ran) or `not-run` (code None, a timeout). `SUMMARY_FAILURE`
moved there from `review/full_check.py`; the Django-only `DJANGO_TEST_COMMAND` and `DJANGO_RAN_NO_TESTS` in
`code/coder_gate.py` are deleted (the existing `NO_TESTS_RAN_OUTPUT` and `test_run_output.matches_no_test` are reused).
`full_check.run`, `coder_gate.run_commands` and `criteria_verdict.judge_item` map the verdict to their own result
names and keep their own CI-only, UNVERIFIED, setup-fault and search-ban handling.

Inputs whose answer changed (three inputs got looser: the first item below, the `criteria_verdict` item on a `!`-negated filtered run and the `full_check` item on `cat run.log`):

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
- `criteria_verdict`: exit 0 from a `!`-negated filtered run (for example `! pytest t.py::test_new` holding
  `1 failed in 0.10s`) was RED, now GREEN.
- `coder_gate` and `criteria_verdict`: exit 0 from `cat run.log` (or any unfiltered search, print or `!`-negated command)
  holding `1 failed, 2 passed` stays a pass: only a command with a step that is not such a program is read for a
  failing summary.
- `full_check`: exit 0 from `cat run.log` (or any such command) holding `1 failed, 2 passed` was `failed (exit 0,
  summary reports failures)`, now `passed`.
- `coder_gate`, `criteria_verdict` and `full_check`: exit 0 from `bash tests/run.sh` holding `1 failed, 2 passed`
  is a failed command (failed-exit-zero), the wrapper having swallowed the runner's exit code.

## Evidence

Judgment: the three pass rules decided the same exit-0 outputs differently (the architect read of 2026-10-29 listed
`full_check.py` around 369, `coder_gate.py` 259-264 and `criteria_verdict.py` 118).

## Result

The table test runs seventeen (command, code, output) rows through `check_verdict` and each of the three callers and gets
one answer per row; the timeout row and the plain-failure row skip `full_check`; the timeout row also skips `criteria_verdict`. Test files for the four modules and the plan-criteria dry run pass.

## Watch

None: see `unmeasured`.

## Back-out

Revert `check_verdict` and its call sites; restore `SUMMARY_FAILURE` in `review/full_check.py`, and
`DJANGO_TEST_COMMAND` and `DJANGO_RAN_NO_TESTS` in `code/coder_gate.py`.
