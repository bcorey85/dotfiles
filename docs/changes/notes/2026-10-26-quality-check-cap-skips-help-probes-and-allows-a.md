---
type: "Change"
change_type: "fixed"
title: "quality-check-cap skips help probes and allows a for-loop repeat"
description: "The cap no longer counts a --help/-h/--version/-V call as a check run, and it allows a check repeated in one for loop over two or more values, so a flake check runs the same command N times without flag dodges."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T11:42:53-05:00"}
seq: 52
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_help_probe_is_never_denied_and_never_recorded"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A check step with `--help`, `-h`, `--version` or `-V` as a whole word is never denied and never recorded.
- A check inside a `for` loop over two or more values (`for i in 1 2 3`, `$(seq 3)`, `$(seq 1 3)`, `{1..3}`) is never
  denied, and is still recorded, so a plain rerun after it stays denied. A one-value loop, a `while`/`until` body, an
  `if` body and a bare `true;` stay capped.
- The gate now sees checks inside loop and `if` bodies at all. Before, a `do pytest` step never matched, so a loop or
  `if` body was neither capped nor recorded.
- The deny text names the loop form for a deliberate repeat.

## Evidence

- Two peer reports: coders changed flags to dodge the cap on a three-run flake check, and the cap denied a required
  `cargo test --help` probe during planning.
- Six new tests fail on the base commit and pass after.

## Result

- Full suite and ruff pass on the worktree.

## Watch

—

## Back-out

Revert the commit.
