---
type: "Change"
title: "Python hooks start through a launcher that skips the pyenv shim"
description: "Every Python hook in settings.json runs through scripts/tools/hook-python, which finds a real interpreter without starting pyenv, so a tool call no longer waits 1-2 s on a version manager's shim."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T17:30:40-05:00"}
seq: 117
kind: "fix"
components: ["rule/settings-json", "script/hook-python"]
evidence: ["timing"]
watches: []
test: "tests/scripts/test_hook_python.py::SettingsHookCommandsTest::test_every_python_hook_runs_through_the_launcher"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/tools/hook-python` (POSIX sh). It runs the hook script on pyenv's global version, read from
  `$PYENV_VERSION` or `$PYENV_ROOT/version` without starting pyenv; if that version name (a prefix such as `3.12`)
  has no `versions/<name>/bin/python3`, it falls back to the `python3` shim, slow but correct; with version `system`
  or none, it runs on the first `python3` on PATH outside a `shims` folder, else on plain `python3`.
- The 42 Python hook commands in `settings.json` change from `python3 ~/.claude/<script>` to
  `sh ~/.claude/scripts/tools/hook-python ~/.claude/<script>`. `sh` runs the launcher, so it needs no exec bit.
- `test_oldest_python_syntax` reads the hook scripts from the new command form.

## Evidence

- With `python3` resolving to the pyenv shim, the shim took 1.2-2.3 s per call, and the same interpreter called by
  its versions path took under 30 ms. A Bash call fires up to 14 Python hooks (12 before the call, 2 after), and an Edit or Write fires 8.
- Timed: the Bash call's hooks, all of one event at once, as the harness runs them. With a stand-in shim that waits
  1.2 s first on PATH, PreToolUse went from 1276 ms to 77 ms (median of 3), and PostToolUse from 1239 ms to 36 ms. On
  this machine, where `python3` is the system interpreter, PreToolUse stayed at 78-79 ms: the launcher adds no
  measurable time.
- Seven launcher tests cover each lookup step. The settings test fails on the base tree.

## Result

- A machine with pyenv runs every hook on pyenv's global version (or `$PYENV_VERSION`), without the shim's start-up;
  a version name the launcher cannot find falls back to the shim. A `.python-version` file in a repo no longer changes
  which interpreter the hooks use.

## Watch

—

## Back-out

Revert the commit.
