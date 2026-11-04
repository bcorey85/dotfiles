---
type: "Change"
change_type: "fixed"
title: "Full check runs the repo's own test command before a pytest guess"
description: "A repo with no check command but a Makefile test target, or else a package.json test script, gets that command in its discovered full check in place of a guessed pytest or JS runner."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T19:20:10-06:00"}
seq: 7
kind: "fix"
components: ["script/check-discovery", "script/full-check"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_check_discovery.py::CheckDiscoveryTest::test_a_unittest_repo_with_a_makefile_test_target_runs_make_test_not_a_pytest_guess"
asked: ""
proof: []
unmeasured: "One work incident; no intake number counts discovered full checks by source."
---

## Change

`check_discovery.py` keeps its order: `make check`, then the package.json `check` script, then the joined parts. In the parts, the test step is now the repo's own test command when it names one: `make test` for a Makefile `test` target, else `<package manager> test` for a package.json `test` script. Only a repo that names neither gets a guessed runner (vitest or jest from the dependencies, `manage.py test`, pytest). Lint, type check and ruff stay ahead of the test step. A repo whose only signal is a Makefile `test` target now gets `make test`, where it got no full check before.

## Evidence

In /code on a unittest repo, the review loop's full check ran `.venv/bin/python -m pytest` with no pytest installed and reported a critical blocker, while `make test` passed.

## Result

Three new tests fail on the base commit and pass after: the unittest repo with a Makefile `test` target gets `make test`; a Makefile `test` target wins over a package.json `test` script and its vitest dependency; a package.json `test` script wins over a pytest guess. The old test that a Makefile with only a `test` target gives no check now uses a Makefile with neither target. `test_full_check.py` and `test_gate_commands.py` pass unchanged.

## Watch

None.

## Back-out

Restore `makefile_check_command`, drop `own_test_command` and the `guesses_tests` parameters, and put back the `elif "test" in scripts` branch in `package_part_commands`.
