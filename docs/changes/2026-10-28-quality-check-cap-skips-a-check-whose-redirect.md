---
type: "Change"
change_type: "fixed"
title: "quality-check-cap skips a check whose redirect failed and dates a run at its start"
description: "The cap recorded a check whose output redirect could not be opened, so the check never ran, and then denied every rerun of it. It also dated a run at its end, so an edit made while the check ran did not count. A check whose redirect the shell could not open is not recorded, and a run record keeps the run's start."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T00:51:35-05:00"}
seq: 155
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_check_whose_redirect_could_not_be_opened_never_ran_and_is_not_recorded"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `quality_check_cap.py`: a check step's output redirections (`>`, `>>`, `2>`, `&>`) are read with the shared shell
  parser, resolved against the step's cwd. After the call, a check is not recorded when the shell could not open a
  redirect into a missing folder. An output file the command deleted itself is no
  failure. A target with a variable, a glob or a substitution, and a `/dev/` path, are left out, so such a run is
  recorded as before.
- When the cap lets a check start, it writes a start mark. The run record keeps that start in a line, while its own
  time stays at the run's end. An edit made after the start, including one made while the check ran, allows the rerun;
  a file the check itself wrote is older than the record, so it does not. With no start mark, or in a command that
  holds a formatter, the run counts as started just after the last edit, as before. A call that skips the cap
  (`#skip-quality-cap`) or is exempt through a formatter clears the start marks.
- The deny text says the repeat loop runs over two or more values, since a one-value `for` loop stays capped.
- Closes the queue items quality-check-cap-counts-a-check-whose-output, quality-check-cap-counts-a-run-whose-output and
  quality-check-cap-refuses-a-subagent-s-test-run.

## Evidence

- A session's lint run redirected into a deleted scratch folder: the shell failed the redirect, the cap recorded the
  run, and every rerun, including the /tmp/check.log form its deny text suggests, was denied as unchanged.
- The redirect test, the edit-during-a-run test and the deny-text test fail before the change. The test of a subagent
  that edits after the session's run and then runs the target once passed before too: with an agent id or with an edit
  seen by the hook, the cap already allowed it.

## Result

- The cap's tests pass, ruff is clean, and the full suite passes.

## Watch

—

## Back-out

Revert the commit. A check whose redirect failed counts as run again, and a run is counted from its end.
