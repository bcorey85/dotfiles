---
type: "Change"
change_type: "fixed"
title: "The full check reads the dotfiles suite's total line as its summary"
description: "runner_summaries reads the dotfiles suite runner's total line, so a passing dotfiles full check reads passed, not unverified, and a total with failed files reads failed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T08:07:17-05:00"}
seq: 177
kind: "fix"
components: ["script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_test_run_output.py::MatchesNoTestTest::test_the_dotfiles_suite_total_is_the_summary_of_a_passing_run"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/test_run_output.py` adds one summary pattern: the suite runner's total line,
`N tests in M files, wall-clock ..., K failed`, with N above zero. The review loop's full check takes it as the
runner summary, so a passing `bash tests/run.sh` reads `passed` with the total as its summary. A total with K above
zero already matches the full check's failure pattern, so it reads failed even on exit 0. A total of zero tests is
no summary and stays unverified.

## Evidence

Every dotfiles review read its full check as `unverified (exit 0, no runner summary)`: the suite prints per-file
lines and one total line, and no runner pattern matched either.

## Result

The new pass-case test fails before the change (no summary) and passes after; the K-failed test and two full-check
cases (passed on a 0-failed total, failed on a 1-failed total at exit 0) pass.

## Watch

None: the effect is the full check's own label on dotfiles reviews, read directly.

## Back-out

Revert the commit; the full check reads dotfiles runs as unverified again.
