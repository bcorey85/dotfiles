---
type: "Change"
change_type: "fixed"
title: "Shell write gate reads a process-substitution tee target"
description: "A tee or redirect inside a >(...) or <(...) span is read as gate text, so it is checked like a tee at the top of the command."
generated: {"by": "claude-sonnet-5-5/coder", "at": "2026-11-20T20:41:50-06:00"}
seq: 3
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["review of the shell gates: echo x > >(tee tracked.txt) wrote a tracked file past the gate, which read only $(...) and backtick spans"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_a_tee_inside_a_process_substitution_is_read_as_gate_text"
asked: ""
proof: []
unmeasured: ""
---

## Change

`gates/shell_write_gate.py` reads the text of each outermost unquoted `>(...)` and `<(...)` span (`shell_command.process_substitution_bounds`) as its own gate text, at any depth and inside a `$(...)` span, next to the `$(...)` and backtick spans it already read. A span found twice counts once. A coder's tee target with a glob or brace list inside a span is denied as the same target outside a span is.

## Evidence

`echo x > >(tee tracked.txt)`, `cat <(echo x | tee tracked.txt)` and `echo $(echo x > >(tee tracked.txt))` were allowed before and are denied with `[tracked_target]` now. A quoted `'>(tee tracked.txt)'` and a tee to an untracked file stay allowed.

## Result

The 12002-command replay of real Bash commands (see the computed-target note) was run over the final tree; its verdict changes are listed there.

## Watch

A command that holds `>(` or `<(` in text the quote scan does not see as quoted, and is denied. Each one is the case to review.

## Back-out

Remove the `process_substitution_bounds` loop from the gate's text reader in `gates/shell_write_gate.py`.
