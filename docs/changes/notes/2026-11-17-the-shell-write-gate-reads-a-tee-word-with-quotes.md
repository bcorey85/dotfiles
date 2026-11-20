---
type: "Change"
change_type: "fixed"
title: "The shell-write gate reads a tee word with quotes or escapes as tee"
description: "`t\"\"ee`, `\\tee`, `\"tee\"`, `/usr/bin/tee` and `(tee ...)` are read as tee, so their operands are checked; PRECHECK reads the command with quotes and escapes dropped."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-17T19:33:21-06:00"}
seq: 4
kind: "fix"
components: ["script/shell-write-gate", "script/shell-command"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_a_quoted_tee_word_with_a_tracked_operand_is_denied_for_the_main_session"
asked: ""
proof: []
unmeasured: ""
---

## Change

Two changes. PRECHECK tests the command with `"`, `'` and `\` removed (`shell_quoting.without_quote_characters`), so
`t""ee tracked.txt` no longer skips the whole check. `shell_command_words.raw_word_names_command` reads a raw tee word
with its quotes and escapes removed, and `shell_command_words.command_word_index` takes the tee at the command word only, once
wrappers and a leading `(` are peeled;
a `|&` part of a step is read on its own (`shell_statements.split_on_pipe_both`, shared with the inline-interpreter
hint), so `grep tee *.py |& tee /tmp/a.log` no longer reads `grep`'s `tee` as the command. A tee operand is read
without redirect words (`shell_command.raw_words_without_redirections`), so `tee >/dev/null f` checks `f`, not
`>/dev/null`.

Refactor, no behavior change: `tee_command_words` peels wrappers once and compares the command word through
`shell_command_words.word_names_command`. The parsed reader already read `t""ee` on master.

## Evidence

Queue item `shell-write-gate-precheck-misses-a-split-quote-tee`, filed from this branch's first review round.

## Result

The test fails on master's gate (the tracked write is allowed) and passes now.

## Watch

None.

## Back-out

Test PRECHECK against the command as written, without `shell_quoting.without_quote_characters`.
