---
type: "Change"
change_type: "fixed"
title: "Memory-cap hook skips heredoc bodies and comments"
description: "The memory-cap hook reads a test runner only in the command's shell code, so a quoted heredoc body that names vitest, pytest or tests/run.sh is no longer denied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:28:12-06:00"}
seq: 4
kind: "fix"
components: ["script/memory-cap-scope", "script/inline-interpreter-hint", "script/shell-statements"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_memory_cap_scope.py::MatcherTest::test_passed"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`uncapped_test_run` and `foreground_full_suite` split `shell_statements.shell_code(command)`, which cuts heredoc bodies and comments, in place of the raw command. A body fed to a shell, or piped into one (`cat <<EOF | bash`), is still read: `shell_statements.opens_shell_heredoc` now follows the pipe.

## Evidence

Judgment: the bench build_queue call with two quoted heredoc bodies naming vitest was denied; replayed, it was denied before the fix and allowed after.

## Result

Median hook time over 15 runs (bare `python3 -c pass` 7.9 ms): `pytest -x tests/` 36.0 ms before, 36.8 ms after; a chained pytest 37.5 to 38.3 ms; the bench heredoc call 47.7 to 48.4 ms.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
