---
type: "Change"
change_type: "fixed"
title: "full_check default limit is 1800 s"
description: "full_check.py's default limit rises from 540 s to 1800 s, so a branch-end check of the dotfiles suite (about 870 s) passes and writes its receipt."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:28:12-06:00"}
seq: 5
kind: "fix"
components: ["script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::DefaultLimitTest::test_a_run_with_no_timeout_gets_a_limit_above_a_normal_dotfiles_suite_run"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`DEFAULT_TIMEOUT_SECONDS` is 1800. close-branch, the only caller without `--timeout`, now gets a limit above the suite's wall time; a call past the Bash tool's 600 s ceiling moves to the background and still finishes.

## Evidence

Judgment from the queued report: a 540 s run ended `not run (timeout)`; a rerun with `--timeout 1800` passed in 870 s.

## Result

The new test pins that a run with no `--timeout` gets the default, and that it is at least twice the suite's 870 s.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
