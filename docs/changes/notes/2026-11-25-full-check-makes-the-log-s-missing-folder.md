---
type: "Change"
change_type: "changed"
title: "full_check makes the log's missing folder"
description: "full_check.py creates the --log path's missing parent folders before it opens the log, so a log in a missing folder no longer ends the run with a FileNotFoundError traceback."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T15:17:36-06:00"}
seq: 3
kind: "fix"
components: ["script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_log_under_a_missing_folder_runs_the_check_and_writes_the_log"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`run_check_command` makes the log's parent folders (`mkdir(parents=True, exist_ok=True)`) before it opens the log. Every
caller of `run` gets it.

## Evidence

Judgment: a session's background full check with `--log` in a missing verify-output folder died with FileNotFoundError
after the receipt row was written. The new test failed with that error before the change.

## Result

A full check with a log in a missing folder runs and writes the log; the session no longer makes the folder and reruns.

## Watch

None: the change only adds folders on the log's own path.

## Back-out

Revert the commit: a missing log folder raises FileNotFoundError again.
