---
type: "Change"
change_type: "fixed"
title: "Deferred findings reach a resumed /review fix run through --also-fix"
description: "`review_fix.py launch --also-fix <file>` adds findings to the fix run after the `--fix` ones, and the code-fork's denied write under `<git dir>/review-fix/` now names that route."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T10:08:11-06:00"}
seq: 3
kind: "fix"
components: ["script/review-launch", "script/review-fix-asks", "script/fork-write-scope", "script/review-fix-names"]
evidence: ["review-fix-coder-ignores-a-no-code-ask-ruling"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_also_fix_findings_follow_the_fix_findings_and_the_run_folder_file_is_consumed"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_launch.py`: `launch --also-fix <file>` reads the file through `read_findings_file` and appends its findings after the `--fix` findings, so `--user-ruled` and `--session-ruled` numbers keep their meaning. A run-folder file is consumed like the other inputs; `relaunch_args` leaves it out. `--also-fix` without `--fix` stops the launch.
- `gates/fork_write_scope.py`: a code-fork Write under `<git dir>/review-fix/` is still denied (fail-closed), and the deny text names `<run folder>/fix-findings.md` and `--also-fix`. The file name lives in `lib/review_fix_names.py`.
- asks-done's printed launch output names the same route.
- `gates/fork_write_scope.py`: the deny text now starts with `fork_write_scope: `, so every deny names the gate.

## Evidence

Queue item `review-fix-coder-ignores-a-no-code-ask-ruling`, part 2: on `/review resume` the code-fork tried to write deferred findings into `<git dir>/review-fix/ask-findings.md`; `gates/fork_write_scope.py` denied it (code-fork writes only its run folder) and a Bash heredoc retry hit `indirect_shell`. The findings never reached the fix coder. The same lane hit it twice.

## Result

The named test, `test_also_fix_without_fix_stops_the_launch` and `test_fork_write_scope.py::ForkWriteScopeTest::test_a_review_fix_path_is_denied_and_the_reason_names_the_also_fix_route` fail on the old scripts and pass with the change. No test covers the asks-done sentence.

## Watch

None. No intake number reads this.

## Back-out

Revert the commit. The gate denies the same writes before and after; only its text changes.

