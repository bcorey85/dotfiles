---
type: "Change"
change_type: "fixed"
title: "The review loop's full check refuses a scoped command"
description: "`full_check.run`, which the review loop calls, now refuses a command that names files or tests, or whose scope cannot be read, as `full_check.py` already did from the command line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T20:00:00-05:00"}
seq: 294
kind: "fix"
components: ["script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_run_refuses_a_scoped_or_unresolved_command_as_main_does"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `full_check.run` returns `not run (scoped command: ...)` or `not run (unresolved command: ...)` for a command that
  is not declared. A new `declared` argument says whether the command, before its Expected red steps were left out,
  equals the `Quality check:` command; left out, a command that equals it or is && steps of it counts as declared.
- `main()` passes `declared` and no longer refuses on its own. It now judges the scope of the command left after the
  Expected red steps are cut, as the review loop does: a scoped step that is not expected red is still refused.
- The same bug was fixed again as seq 282, "the full check refuses a scoped command for every caller". The merged
  code keeps this change's `declared` argument, and `base_run` passes `declared=True`.

## Evidence

- The scope refusal lived only in `main()`. The review loop calls `run()` directly, so a check the finder named on
  files or tests ran, could print `passed`, and the stop gate counted it as a full check.

## Result

- The named test fails before (`run()` ran the scoped and unresolved commands) and passes after.
  `test_run_runs_the_declared_check_with_its_expected_red_steps_left_out` keeps a trimmed declared check running.

## Watch

—

## Back-out

Revert the commit.
