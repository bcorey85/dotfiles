---
type: "Change"
change_type: "fixed"
title: "shell-write-gate in-place denial names the session temp root"
description: "An in-place edit of an untracked file outside the session temp root is denied with the temp root named, so an agent with no Write or Edit has a path it can follow."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T18:56:05-06:00"}
seq: 5
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_in_place_deny_of_an_untracked_file_names_the_session_temp_root"
asked: ""
proof: []
unmeasured: "Two architect stops in one eng-spec run; no intake number counts gate-stopped probes."
---

## Change

When the gate denies an in-place edit (`sed -i`, `perl -pi`, `awk -i inplace`) of a file that is not git-tracked, the denial adds "An in-place edit of a scratch file under /tmp/claude-<uid> passes." A tracked target gets no such line and stays denied as before. The exemption for files under the session temp root already existed (39743d2e); only the advice changed.

## Evidence

Two read-only architects in one eng-spec run hit the denial on a /tmp scratch file. The denial said to use Write or Edit, which they lack, so each probe stopped.

## Result

The new test failed before the change (the reason did not name `/tmp/claude-1000`) and passes after; it also asserts a tracked target's denial does not name the root. Gate median wall time over 120 runs (4 commands × 30, architect subagent payload): 33.3 ms before, 33.6 ms after.

## Watch

None.

## Back-out

Remove the `is_git_tracked` branch that appends the temp-root line in `run()` and the `claude_temp_root` import.
