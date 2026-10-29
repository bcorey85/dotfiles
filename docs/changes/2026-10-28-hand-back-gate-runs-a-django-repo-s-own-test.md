---
type: "Change"
change_type: "fixed"
title: "hand-back gate runs a Django repo's own test runner when the plan lists none"
description: "With no usable test command in the plan, the hand-back gate ran bare pytest in a Django repo with no pytest-django settings, so collection failed on missing settings and the gate spent its denials on a non-code error. It now runs manage.py test on the changed test modules, a Django settings error under pytest is a setup fault, and a manage.py test run that ran no test is no pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T01:16:00-05:00"}
seq: 152
kind: "fix"
components: ["script/coder-gate", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_django_repo_without_pytest_django_settings_runs_manage_py_test_on_dotted_labels"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_gates.py`, when the phase lists no Python test command the gate can take:
  - A repo with a root `manage.py` and no pytest-django settings (`DJANGO_SETTINGS_MODULE` or `--ds` in `pytest.ini`,
    `tox.ini` `[pytest]`, `conftest.py`, pyproject `[tool.pytest.ini_options]` or setup.cfg `[tool:pytest]`) runs
    `<runner> manage.py test <labels>` on the changed test modules as dotted labels. A repo with those settings keeps
    pytest.
  - A listed whole-suite `manage.py test` command gives its runner and options; its labels go before the options. It
    wins over pytest-django settings.
  - A listed whole-suite pytest command keeps pytest.
  - A Django phase that names no test file gets no test command, since a bare `manage.py test` runs the whole suite.
- `check_output.py` `is_django_settings_fault`, used by the coder gate only: under a pytest command, a Django settings
  error (ImproperlyConfigured, "settings are not configured", "Apps aren't loaded yet") with no failed test and no
  SyntaxError is a setup fault, unless the coder changed a `*settings*.py`, a file under `settings/`, or an `apps.py`.
  Under `manage.py test` a settings error stays a failure. The full check keeps its rule.
- `coder_gate.py` `run_commands`: a `manage.py test` run that exits 0 with "Ran 0 tests" is a setup fault, so the gate
  result is `setup-fault`, not `pass`. `check_output.py` reads "Ran 0 tests" as a run that found no test.
- Limits: only a root `manage.py` is recognised.
- Closes the queue items hand-back-gate-runs-bare-pytest-on-a-django-repo,
  hand-back-gate-runs-django-backed-tests-through and hand-back-gate-runs-django-tests-with-bare-pytest.

## Evidence

- A /code run's gate ran bare pytest over a Django project's tests. Collection failed with ImproperlyConfigured, the
  gate hit its three-denial cap and handed back as failing, and the same modules passed under `manage.py test`.
- The new derivation, settings-error and ran-no-test tests fail before the change.

## Result

- The code_step, coder_gate and check_output tests pass, and ruff is clean.

## Watch

—

## Back-out

Revert the commit. The gate runs bare pytest in a Django repo whose plan lists no test command again.
