---
type: "Change"
change_type: "fixed"
title: "Quality-check cap skips a check that stopped on a missing path"
description: "A failed check whose output says it stopped on a path that does not exist (ruff E902, pytest file not found, mypy can't read file) never ran on the files, so the quality-check cap no longer counts it as a failed attempt."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T16:49:36-06:00"}
seq: 10
kind: "fix"
components: ["script/quality-check-cap", "script/check-output"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_check_that_stopped_on_a_missing_path_never_ran_and_is_not_recorded"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/check_output.py` gains `stopped_on_missing_path(output)` (ruff `E902 No such file or directory` in both formats, mypy `can't read file`, and the existing `missing_path` lines). `gates/quality_check_cap.py` returns before recording a PostToolUseFailure whose error text matches it.

## Evidence

judgment: a session passed a file list as one quoted word; ruff stopped on E902 and the cap counted it as a failed approach. All four cases of the new test fail on the base commit and pass after. Hook median on a PostToolUseFailure E902 event: 90.4 ms on the branch against 89.4 ms on master (11 runs each), next to about 11.7 ms for a bare Python start.

## Result

`test_quality_check_cap.py` 99, `test_check_output.py` 44, `test_full_check.py` 71: all pass; lint clean.

## Watch

—

## Back-out

Remove `stopped_on_missing_path`, `CHECK_MISSING_PATH` and the early return in `quality_check_cap.run`.
