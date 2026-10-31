---
type: "Change"
change_type: "fixed"
title: "bash-safety-gate pipe-to-shell rule reads real pipes only"
description: "The pipe-to-shell rule no longer denies a pipe character inside a quoted argument, such as the regex (py|sh)."
generated: {"by": "claude-code/sonnet-5-5", "at": "2026-10-25T22:55:34-05:00"}
seq: 28
kind: "fix"
components: ["script/bash-safety-gate", "script/pipe-shell-check", "script/shell-command"]
evidence: ["repro"]
watches: []
test: "tests/scripts/test_bash_safety_gate_pipe_shell.py::PipeShellRuleTest::test_a_pipe_character_inside_a_quoted_argument_is_allowed"
asked: ""
proof: []
unmeasured: ""
---

## Change

The pipe-to-shell rule in bash-safety-gate.sh matched a pipe character followed by sh, bash, zsh, dash or ksh anywhere in the command text. It now runs tools/pipe_shell_check.py when the text holds a pipe and a shell word. The check reads the command with lib/shell_command.py, which gained parse_piped_commands (the existing parse_simple_commands now wraps it) so each simple command says whether a real pipe comes right before it. It denies a piped command that runs a shell, also behind sudo, env, exec and similar wrapper words, and a `{` group word. A command the parser cannot read falls back to the old text match. The generator for bash-safety-gate.sh is not on this machine, so the edit was made in place; carry it into the generator.

## Evidence

A read-only agent ran a ripgrep into a grep with the regex (py|sh) and was denied. The same false match denied a heredoc that wrote a Python script with such a regex inside it; both now pass. A heredoc body holding a bare piped-into-sh line is still denied, because the parser reads heredoc bodies as commands (a different cause, left as is). The pre-existing fast path in the gate reads one line at a time, so a pipe at the end of a line with the shell on the next line is not seen; that was true before and is unchanged.

## Result

One call instead of a rewritten query that dropped the sh branch.

## Watch

None: the hook block log shows the rule by reason tag.

## Back-out

Restore the grep line of the pipe-shell rule in bash-safety-gate.sh, delete tools/pipe_shell_check.py and parse_piped_commands in lib/shell_command.py.
