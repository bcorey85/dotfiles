---
type: "Change"
change_type: "fixed"
title: "test_run_output counts a passing unittest run and ignores colour escapes"
description: "A unittest run that prints `Ran N tests` and then `OK` counts N passed tests, so a filtered `-k` run is no longer rejected as \"exits 0 but ran no test\"; ANSI colour escapes around runner count words no longer hide the count."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T09:35:35-06:00"}
seq: 2
kind: "fix"
components: ["script/test-run-output", "script/refactor-flow"]
evidence: ["scoped-test-check-calls-a-passing-unittest-run-a"]
watches: []
test: "tests/scripts/test_test_run_output.py::MatchesNoTestTest::test_a_filtered_unittest_run_that_passed_is_not_a_no_match"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `lib/test_run_output.py` `passed_test_count` adds N for each unittest/Django `Ran N tests` summary whose next line starts with `OK` (also `OK (skipped=k)`: a skipped test counts as ran). `Ran 0 tests` and a `FAILED (...)` run still count none.
- `passed_test_count` and `runner_summaries` strip ANSI CSI escapes before matching, so a coloured vitest `2 passed` counts.
- New `lib/ansi_text.py` `strip_ansi` owns the escape pattern; `skills/refactor/scripts/refactor_flow.py` drops its inline copy and imports it.
- Test harness lib lists (`tests/scripts/toolkit_paths.py`, `test_review_commit_gate.py`) and `docs/toolkit-script-rules.md` name the new module.

## Evidence

Queue item `scoped-test-check-calls-a-passing-unittest-run-a`: a coder hand-back running `python3 -m unittest discover ... -k a -k b` (Ran 4 to 17 tests, OK) was rejected three times by the review loop and the hand-back gate, and the loop ended critical-blocker.

## Result

Eight new tests in `tests/scripts/test_test_run_output.py` plus `tests/scripts/test_ansi_text.py`; the named test and three others fail on the old script. Sweep over 13,439 runner-summary tool outputs under `~/.claude/projects/`: counted above zero 8,638 before, 11,514 after; all 2,948 passing unittest outputs count (2,874 read as zero before). The rest are non-passing text (failed Django runs, diffs, panics), spot-checked, not each verified.

Suite: `bash tests/run.sh` passes, 4185 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
