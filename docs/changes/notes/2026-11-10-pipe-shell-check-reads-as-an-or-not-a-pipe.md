---
type: "Change"
change_type: "fixed"
title: "pipe-shell check reads || as an OR, not a pipe"
description: "The pipe-shell check script and its gate-replay reference no longer read the second bar of `||` as a pipe into a shell, so `a || bash <script> list` passes there; the live generated bash-safety-gate.sh grep still denies it. A real `| sh` and a bar behind an odd run of backslashes still deny."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T17:43:08-06:00"}
seq: 4
kind: "fix"
components: ["script/pipe-shell-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pipe_shell_check.py::PipeShellCheckTest::test_a_command_with_no_pipe_into_a_shell_is_allowed"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/tools/pipe_shell_check.py`: the text fallback's regex skips a `|` that follows another `|`, unless an odd run
of backslashes comes before the first bar (then it still denies, fail closed). An even run is escaped backslashes, so
the bars after it are a real `||` and pass. Any quoted text in a command that names a code runner keeps the stricter
reading: any backslash run before the bars denies (fail closed). The module docstring no longer claims that a
quoted pipe passes.

## Evidence

judgment: the denied command was reproduced against the script; the test case `a || bash /x/h list` fails before the
change.

## Result

The new allowed cases pass and every denied case still denies. The script's median time on four matched commands is
22.0 ms, next to 11.6 ms for a bare `python3 -c pass`.

No live hook calls this script: the generated `bash-safety-gate.sh` runs its own grep for `pipe_shell` (its grep at
line 307; the block call is at 308), which still denies `||`. That rule is owned by the work machine and is logged in
`~/agent-evals/WORK-SECURITY-HOOKS.md`. This script stays the gate replay's reference.

## Watch

None: the script has no live caller, so no intake number reads it.

## Back-out

Revert the commit.
