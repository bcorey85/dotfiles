---
type: "Change"
change_type: "fixed"
title: "The shell-write gate denies a coder redirect or tee target that zsh expands"
description: "A coder's redirect or tee target with an unquoted brace list, glob character, glob qualifier or a leading `=command` is denied whole, since zsh can land it outside the temp dir the literal text names."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-17T19:33:21-06:00"}
seq: 2
kind: "fix"
components: ["script/shell-write-gate", "script/shell-command"]
evidence: ["census", "tests"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_a_coder_target_that_zsh_expands_is_denied_as_a_new_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

`deny_expanding_targets` runs for a coder before PRECHECK. It reads each raw redirect target word
(`lib/shell_expansion.py` `redirect_target_words`) and each tee operand, and denies `[coder_new_file]` when the word
holds an unquoted `{...,...}`, `*`, `?`, `[` or a glob-qualifier `(` (`f(:s.tmp.etc.)`), or starts with an
unquoted `=name` (zsh EQUALS gives the command's path; a word with an unquoted `$` goes to the variable check). The
inside of `$(...)`, backticks and `${...}` is not read as the word's own; `((...))` and `$((...))` are arithmetic only
when the inner `(` closes at the last character (`shell_statements.arithmetic_spans`, the one owner), so `$((cmd) )`
is read as a command substitution and `((echo hi) > {a,b}); echo $((1))` as a subshell with a target; and `>(cmd)`, `<(cmd)` and `=(cmd)`
are process substitutions, not targets. The gate's target regexes read the forms `>`, `>>`, `>|`, `>!`, `>&`, `>>&`,
`>&|`, `>&!`, `>>&|` and `>>&!` through `shell_command.REDIRECT_OPERATOR`, the one owner of the operator set, with
`shell_command.WORD_END_CHARACTERS`. The command parser in the same module derives `ADJACENT_BANG_CLOBBER` (the adjacent
`>!`, `>>!`, `>&!` and `>>&!`) from the same base, reads `>|`, `>>|`, `&>|`, `>&|` and `>>&|` through `CLOBBER_TOKEN`,
and reads the plain and `&>` forms as redirect characters.

Quote and comment positions moved from `lib/shell_command.py` into `lib/shell_quoting.py`; every caller imports them
from there. `quoted_positions` now reads `$'...'` as ANSI-C quoting (a backslash escapes the quote inside it) and `$$`
as the process id, for all callers (`test_a_quote_after_an_escaped_dollar_or_a_pid_does_not_hide_a_tracked_write`).
`pipe-shell-check` now allows `rg -n 'files=\(|\$files|zsh' a.zsh | head -20`, so the replay corpus case
`psc-rg-alternation-zsh` lost its open note.
An adjacent `>!`, `>>!`, `>&!` or `>>&!` is read as the clobber operator with `|` before lexing
(`shell_command.with_bang_clobber_as_pipe`), so `echo hi >&!tracked.txt` is a tracked write for a non-coder; with a
blank after the `>`, `!name` is a file name, as in zsh. `ssh.exe` and `bash.exe` (WSL) count as code runners again;
`run.sh` and `~/.ssh/config` stay file names.

## Evidence

Queue item `shell-write-gate-lets-perl-0pi-and-a-zsh-brace-or`: `echo hi > /tmp/x/{a,b}` and
`echo hi > /tmp/x/f(:s.tmp.etc.)` passed as scratch paths.

## Result

The new test fails on master's gate (both commands allowed) and passes now. The replay of real coder commands from
local transcripts shows no new coder deny. A runner name inside a file name (`work-intake.sh`, `~/.ssh/config`,
`deploy-script.py`) no longer counts as a code runner (`shell_command.CODE_RUNNERS`), so the quotes of such a command
stay quoted and a `>` inside them is no redirect; before, the unquoted text scan read `'"m":"<s>".*'` as a write to `.*`.
The target regex now ends a word at a newline, so code-runner text is read line by line:
`eval 'echo x > README.md<newline>echo y'` is denied (master read the target as `README.md<newline>echo` and allowed
it). A heredoc body inside code-runner text is read as commands too, so `eval 'cat <<EOF > f<newline>b > *<newline>EOF'`
is denied for every agent. The replay found three such denies, all on this branch's own probe commands and none
on a real one, so it stays a fail-closed deny with no new code.

## Watch

None.

## Back-out

Remove the `deny_expanding_targets` call in `run`.
