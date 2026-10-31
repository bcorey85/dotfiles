---
type: "Change"
change_type: "changed"
title: "Script tests run with one fixed git config so CI and local agree"
description: "The script test runner gives every test process one fixed global git config, no system config, empty ignore and attributes files, and no git config from the environment. The CI workflow loses its own git setup step."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T19:46:07-05:00"}
seq: 22
kind: "behavior"
components: ["script/parallel-tests"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `tests/parallel_tests.py` writes a fixed gitconfig in a `TemporaryDirectory`: user `ci`, `ci@example.com`, `init.defaultBranch = master`, and `core.excludesFile` and `core.attributesFile` set to an empty file. Each worker gets `GIT_CONFIG_GLOBAL` set to that file and `GIT_CONFIG_NOSYSTEM=1`. The runner drops `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT` and every `GIT_CONFIG_KEY_*` and `GIT_CONFIG_VALUE_*` from the worker environment.
- `.github/workflows/script-tests.yml` loses its "Configure git" step.
- In CI, the default branch of a new test repo changes from `main` to `master`. Two code-step tests expect `master`, and the built-in default changes in git 3, so the runner sets it.
- `GIT_CONFIG_GLOBAL` needs git 2.32 or newer.

## Evidence

Work incident: the script test workflow failed on every one of its 15 runs. Since the earlier faults were fixed, every run failed on one test, the case where git refuses a folder and a `.git` entry in a parent decides. Its precondition expects git to refuse the folder. The runner's global config holds `safe.directory = *`, so git accepted the folder and the precondition failed. With the machine's global and system config switched off, git refused again.

Tests: under a hostile config (`safe.directory = *` in the global file and in `GIT_CONFIG_*` environment keys, and a wrong user name), the new runner passed 1484 tests with 0 failures. The installed runner failed the named test under the same config.

## Result

Built 2026-10-21. Installed and pushed the same day. The first CI run after the push passed, the first pass in the workflow's 16 runs.

## Watch

None. No intake metric reads CI runs. Check `gh run list --workflow script-tests.yml` after the push.

## Back-out

Restore the old `parallel_tests.py` and the "Configure git" step in the workflow.
