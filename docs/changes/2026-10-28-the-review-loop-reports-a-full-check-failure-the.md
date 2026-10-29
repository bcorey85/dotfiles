---
type: "Change"
title: "The review loop reports a full-check failure the diff did not cause as pre-existing"
description: "When the full check fails, the review loop reruns it on HEAD without the diff; a failure whose every failing line also fails there is reported as pre-existing, spends no repair coder and does not block."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:43:40-05:00"}
seq: 200
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_full_check_failure_that_also_happens_on_head_is_pre_existing_and_gets_no_repair"
asked: ""
proof: []
unmeasured: ""
---

## Change

`full_check.base_run` runs the check command in a detached worktree of HEAD in a temp dir, with the
repo's node_modules, .venv and venv symlinked in, logs to `full-check-base.log`, and removes the worktree in a
`finally` (and on SIGTERM). `full_check.is_pre_existing` holds when the head run has the same result (exit code) as
the base run, its failing lines are non-empty and a subset of the base run's failing lines, every detail line under
a failing test line (up to the next failing line, across blank lines; jest's `PASS` lines are not details)
also appears under a failing line in the base run, and no other line new to the head log holds an error marker
(error, fail, exception, traceback, panic). Runner timings are ignored, except in a failing test's reason.
On a runner summary line (`1 failed, 10 passed in 1.2s`, vitest `Tests`, jest `Tests:`), the counts of passed,
skipped, total, deselected, warning, xfailed and xpassed tests are ignored, and so is vitest's total
in parentheses; any other line keeps its counts, and so does a failing test's reason after ` - `, compared as
written, whitespace collapsed. Per-run clock lines (jest `Time:`, vitest `Duration`, `Start at`) keep their
label; the time and vitest's parenthetical after it are ignored, and any other text after the time still
compares. No base run is made when the repo's .venv or venv holds any editable
install, or the active virtualenv or conda environment holds one that points into the repo, or a node_modules symlink
resolves into the repo: the links would load the diff's own files. No base run is made either when the check
command or a value of the environment assignments the gate adds names the repo path, or when an inherited PYTHONPATH
or NODE_PATH entry points into the repo. The result reads
`pre-existing failure (the check fails the same way without this diff, so it did not verify this diff)`: not a failure
and not a setup fault. A check that stops early on the old failure (lint before test, a collection error,
`-x`) never ran the diff's tests, so this result says the diff was not verified, not that it is clean. The loop
compares on every failing check, before the repair coder, runs the base at most once per loop and reuses its lines
after the class repair. The hand-back packet shows the result. A diff that adds a new failing test or lint
line, or any new line with an error marker, is still a failure. When every failing line is a `FAILED: <steps>`
summary, the failure is pre-existing only if no line at all is new to the head log, because the summary names
steps, not what failed in them. The code step counts the base log as progress, so a long base run restarts its
wait cap. Before the base run the gate sweeps only its own `full-check-base` folder for trees older than twice the
check timeout, and never runs a repo-wide worktree prune.

Cost: one extra full check run, up to 900 s, per loop whose full check fails (made once per loop,
pre-existing failures included).

## Evidence

Two consecutive review runs of one phase ended "full check still failing after one repair" on the same check, from
a tool the phase did not touch; each rerun paid for a full review and a repair coder that could not fix it.

## Result

The new loop test fails before (a repair coder runs and the loop blocks) and passes after; base-comparison,
new-line-on-top and run-once tests pass.

## Watch

None: the effect is the packet's full-check line, read directly.

## Back-out

Revert the commit; every full-check failure gets a repair coder and blocks again.
