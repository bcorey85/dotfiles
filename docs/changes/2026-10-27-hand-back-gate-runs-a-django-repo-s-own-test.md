---
type: "Change"
title: "hand-back gate runs a Django repo's own test runner and treats settings errors as setup faults"
description: "The coder hand-back gate ran bare pytest in Django repos with no pytest-django settings, so every collection failed on missing settings and the gate spent its three denials on a non-code error. The gate now takes a manage.py test command from the plan or the repo, and a Django settings error or a pytest usage error is a setup fault."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:07:19-05:00"}
seq: 134
kind: "fix"
components: ["script/coder-gate", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_django_settings_errors_and_a_pytest_usage_error_are_setup_faults"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_gates.py`: the gate's Python test command now follows these rules.
  - A phase whose Automated Verification lists a `manage.py test` command runs that command, with its runner and
    flags, on the changed test modules as dotted labels. It wins over pytest-django settings.
  - A phase that lists a pytest command and no `manage.py test` command keeps pytest, also one behind a `cd` or a
    chain.
  - With nothing listed, a repo with a root `manage.py` and no pytest-django settings (`DJANGO_SETTINGS_MODULE` or
    `--ds` in `pytest.ini`, `tox.ini` `[pytest]`, `conftest.py`, pyproject `[tool.pytest.ini_options]` or setup.cfg
    `[tool:pytest]`) runs
    `<runner> manage.py test <labels>`. A repo that has those settings keeps pytest.
  - A Django phase that names no test file gets no test command, since a bare `manage.py test` runs the whole suite.
- `coder_gate.py` `is_setup_fault`: these are setup faults, which never deny the call or count toward the cap:
  - pytest's exit 4 (a usage or config error), with these exceptions: a conftest that failed to load on a missing
    third-party module is still a setup fault, while "file or directory not found", "ERROR: not found:" and a
    conftest that fails on the repo's own code are failures; and exit 4 is a failure when the coder changed a
    settings module, a file under `settings/`, or an `apps.py`;
  - a Django settings error (ImproperlyConfigured, "settings are not configured", "Apps aren't loaded yet") under a
    pytest command with no failed test, unless the coder changed a settings module (any `*settings*.py`), a file
    under `settings/`, or an `apps.py`. Under `manage.py test` the settings load first, so a settings error there
    stays a failure.
  Output with a `SyntaxError` always stays a failure.
- `coder_gate.py` `run_commands`: a `manage.py test` run that exits 0 with "Ran 0 tests" is a failure, so a repo whose
  pytest-style tests the Django runner cannot find never passes the gate on no tests.
- Limits: only a root `manage.py` is recognised, and a test file the coder adds that the phase does not name is not
  run in a Django repo.
- Closes the queue items hand-back-gate-runs-bare-pytest-in-django-repo and
  hand-back-gate-runs-bare-pytest-in-django-repos.

## Evidence

- A /code run's gate ran bare pytest over a Django project's tests. Collection failed with ImproperlyConfigured, the
  gate hit its three-denial cap and handed back as failing, and the same modules passed under `manage.py test`.
- The new setup-fault test and the Django command tests fail before the change.

## Result

- New tests pass, ruff and the gated complexity check are clean, and the full suite passes.

## Watch

—

## Back-out

Revert the commit. The gate runs bare pytest in Django repos again.
