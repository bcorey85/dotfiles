---
type: "Change"
change_type: "fixed"
title: "Deny bare rg with no path before it hangs on stdin"
description: "A Bash call of rg with no path, alone or first in a pipeline, is denied with the same command plus a dot, so the search runs in a second instead of hanging until the timeout."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-25T22:55:20-05:00"}
seq: 29
kind: "fix"
components: ["script/rg-path-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_rg_path_gate.py::RgPathGateTest::test_no_path_is_denied_with_the_fixed_command"
asked: ""
proof: []
unmeasured: ""
---

## Change

New PreToolUse(Bash) hook `claude/.claude/scripts/gates/rg_path_gate.py`, registered in settings.json with
`"if": "Bash(*rg*)"`. It reads the command with the shared parser (`lib/shell_command.py`). An `rg` simple command
with no path operand is denied with the fixed command (the same words plus `.`). A step fed by a pipe
(`cmd | rg foo`), a `<` redirection, `--files`, `--help`, `--version`, `--type-list` and a `-` path pass. `rg foo | head`
is denied, since rg is first in its pipeline. Options that take a value (`-g`, `-e`, `-t`, `-A`, `--glob` and the rest)
are skipped with their value, and `-e`/`-f`/`--regexp`/`--file` mean the first word is a path, not the pattern.

Deny, not rewrite: the hooks docs fetched in this session were cut before the PreToolUse decision-control section, so
whether `updatedInput` works without `permissionDecision: allow` was not confirmed. The one place in this toolkit that
uses `updatedInput` (the hand-back gate) pairs it with allow. A rewrite with allow would skip the permission check.

## Evidence

The Bash tool gives commands a non-tty stdin. `timeout 5 rg foo` from a non-tty exits 124 (timed out); with
`</dev/null` it exits at once. ripgrep documents that it searches stdin when no path is given and stdin is not a
terminal. A reviewer search stalled to the 120 s timeout in a structure-review run. The new test file has 20 tests; the
gate tests fail without the script (file missing).

## Result

Not yet measured at work.

## Watch

None; the gate prints its reason in the tool result, so a bare `rg` shows up as a deny in the hook block log.

## Back-out

Delete the settings.json entry and `gates/rg_path_gate.py`.
