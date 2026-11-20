---
type: "Change"
change_type: "fixed"
title: "The inline-interpreter hint reads redirects through the shared shell parser"
description: "The hint's fallback word splitter drops a redirect and its target through lib/shell_command.py, so a clobber redirect (`>! out.txt`, `>>| out.txt`, `&>| out.txt`) after a bare `python3` no longer reads as a script argument."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-17T19:33:21-06:00"}
seq: 3
kind: "fix"
components: ["script/inline-interpreter-hint", "script/shell-command"]
evidence: ["census", "tests"]
watches: []
test: "tests/scripts/test_inline_interpreter_hint.py::InlineInterpreterHintTest::test_inline_and_stdin_code_is_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

`inline_interpreter_hint.py` dropped its own `REDIRECT_OPERATOR` and `REDIRECT_WORD` regexes. Its fallback splitter
calls `shell_command.is_redirect_word` and `redirect_takes_next_word`. `cat x | python3 >! out.txt` now reads as
`python3` fed stdin code and is denied; `cat x | python3 script.py &> out.txt` stays allowed. The parser reads an
adjacent `>!` as `>|` before lexing, so `> !name` is a file name, not a clobber. `split_on_pipe_both` moved to
`lib/shell_statements.py`, shared with the shell-write gate.

## Evidence

Queue item `inline-interpreter-hint-reads-redirects-with-its`: the hint and `lib/shell_command.py` disagreed on
redirect words.

## Result

Of the five `unparsed_*clobber_redirect_after_python` cases, four fail on master's hint and pass now: `>!` (twice,
one with a trailing `echo '|'`), `>>|` and `&>|`. The `>|` case passes on both. The parser also reads the adjacent
`>&!` and `>>&!` as clobber operators (`>&|`, `>>&|` to the lexer).
`unparsed_python_script_with_both_streams_redirect` stays allowed. The replay changed 11 hint verdicts. Ten are
deny to allow on one probe-harness command that pipes JSON into `python3 <script>.py`; the old deny was false. One
is allow to deny: a `cat > cases.txt <<'CASES'` whose quoted heredoc body holds `perl -0pi -e` lines. The hint
already denies `perl -e` text in a quoted heredoc body on master (a known false deny, moved to
WORK-SECURITY-HOOKS.md); master allowed this one only because it misread `$'it\'s'` earlier in the body as an open
quote that hid the `perl -e` text.

## Watch

None.

## Back-out

Restore the two regexes and the old loop in `split_part_reads_stdin_code`.
