---
type: "Change"
title: "The review loop runs the autofix formatters before a full-check failure blocks"
description: "The review loop runs the autofix formatters on touched files and reruns a failing full check once."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:43:40-05:00"}
seq: 190
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_formatter_fix_clears_the_failure"
asked: ""
proof: []
unmeasured: ""
---

## Change

`recheck_full_check` runs `format_files.run_formatters` (with `configured_only=True`) on the loop's touched files
before it stops as `critical-blocker`. Web files get the oxlint or eslint `--fix` and oxfmt or prettier commands only
when the repo configures them or holds them in `node_modules/.bin`; `.py` files get `ruff check --fix` whenever ruff
is on PATH and the repo configures ruff, and `ruff format` only when the repo formats with ruff (a format table, a
pre-commit entry or `ruff format` in the check command). Plan files and missing files are skipped. When a
formatter changed a file, the check reruns once and the changed files count as touched; otherwise the loop stops as
before. The formatter commands moved out of the `format_changed` hook into `lib/format_files.py`, which the hook now
calls with its behavior unchanged (it still leaves `.py` files alone).

## Evidence

Twice on one branch the run ended "full check failing after the class repair" or "full check still failing after
one repair" on a line-length or prettier error alone; the class-repair coder gets no repair round, so a mechanical
slip blocked a finished review.

## Result

The new loop test fails before (the loop blocks) and passes after; the no-change test confirms no third check run;
the format_changed tests pass untouched.

## Watch

None: the effect is the loop's stop status, read directly.

## Back-out

Revert the commit; a format-only failure after a repair blocks again.
