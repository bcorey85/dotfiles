---
type: "Change"
title: "The test suite lints the toolkit Python"
description: "`tests/run.sh` runs ruff over the toolkit scripts and their tests before the test run. An unused import, an unused variable or an undefined name fails the suite. A report of functions over complexity 10 prints but does not fail. Five files lose an unused import."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T23:21:28-05:00"}
seq: 9
kind: "behavior"
components: ["script/calibration-guard", "script/claudemd-linecount", "script/comment-bloat-gate"]
evidence: ["census", "tests"]
watches: []
---

## Change

- **New `ruff.toml`** at the dotfiles root, scoped to `claude/.claude/scripts` (with the extensionless `verify-log` and `verify-prep`), `claude/.claude/skills/*/scripts` and `tests/scripts`. Pyflakes rules, max complexity 10.
- **`tests/run.sh`:** a pyflakes finding fails the run, after the tests run. The complexity report names each function over 10 and does not fail the run. If ruff is not installed, the run prints a note and goes on.
- **Unused imports removed** from `calibration-guard.py`, `claudemd-linecount.py`, `comment-bloat-gate.py`, `test_agent_cost.py` and `test_log_spec_run.py`. The scripts behave the same.

## Evidence

Census: before this change, no linter, formatter or type checker ran on the toolkit Python. A first ruff run found 11 pyflakes findings and 29 functions over complexity 10, 11 of them in code-step.py. Since 2026-10-19, commits touched those 11 code-step functions 3.6 times each, against 0.6 for the other 177. Tests: the five changed files' tests pass (80 tests).

## Result

Built, and waiting for install after the code-step resume change, which fixes the other four pyflakes findings in its own files. The complexity report becomes a failing check after the code-step simplify pass.

## Watch

None. The suite output shows the counts.

## Back-out

Delete `ruff.toml`, and restore `tests/run.sh` and the five files from the dotfiles history.
