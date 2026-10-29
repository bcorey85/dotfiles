---
type: "Change"
change_type: "fixed"
title: "The dotfiles suite fails when ruff is missing"
description: "tests/run.sh stops with exit 1 and an install line when ruff is not on PATH, where it used to print 'lint skipped' and pass, so a lint or complexity defect can no longer ship through a suite run on a machine without ruff."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T20:15:18-05:00"}
seq: 15
kind: "fix"
components: ["script/run-sh"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_run_sh.py::RunShTest::test_a_missing_ruff_stops_the_run_before_any_test_with_how_to_install_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

`tests/run.sh`: when `command -v ruff` finds nothing, the run prints
`ruff not installed: install it (pacman -S ruff, brew install ruff or pipx install ruff) and rerun` and exits 1
before the duplicate-code check and the tests. It used to print `ruff not installed: lint skipped`, run the rest and
exit 0.

It stops at once, not after the tests. A missing tool is a setup error, and a full run that is bound to fail costs
minutes for nothing.

New test `tests/scripts/test_run_sh.py` runs `run.sh` with a PATH that holds only `dirname`.

## Evidence

On 2026-10-25 a full suite run on a lane branch passed 2110 tests and exited 0, but its first line was
`ruff not installed: lint skipped`. ruff was then only in Neovim's mason folder, off PATH, so every shell run on this
machine skipped lint and C901 while lanes reported lint clean.

The new test fails on the old `run.sh` (exit 0 is not 1, and the skip line has no install hint) and passes on the new one.

## Result

ruff 0.16.6 is now on PATH at `/usr/bin/ruff` (Arch package), so a Claude Code shell runs the lint step.

## Watch

None. Suite setup has no intake number.

## Back-out

Revert the commit.
