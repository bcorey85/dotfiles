---
type: "Change"
change_type: "fixed"
title: "Inline-interpreter hint lets a script run whose quoted argument names a dash-C flag"
description: "A script run such as `python3 bin/build_changes.py new \"Commit with git -C alone\"` now runs without rewording. The hint blanks quoted text before it matches the inline-code rule, as the safety gate does, and still denies `python3 -c`, `node -e` and a quoted flag before the script file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T21:13:42-05:00"}
seq: 415
kind: "fix"
components: ["script/inline-interpreter-hint"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_inline_interpreter_hint.py::InlineInterpreterHintTest::test_a_script_file_module_or_version_flag_is_allowed"
asked: ""
proof: []
unmeasured: ""
---

## Change

`inline_interpreter_hint.py` matches its inline-code pattern on the command with every quoted character replaced by `_`. A `-c`, `-C` or `-e` inside a quoted argument no longer reads as an interpreter flag. The safety gate blanks quoted text the same way, but only on a command it judges read-only. On any other command (a write redirect, a non-read-only step) the gate matches raw text and still blocks a quoted `-c`, with its bare block text. The hint is advice and the gate enforces, so this gap costs only the hint's advice on those rare commands.

Review proposed a faithful copy of the gate's read-only judgment (about 200 lines of the generated gate's awk, ported to Python) or a second gate run inside the hint. Both were declined: the copy drifts with each gate release, and a second gate run doubles its cost and writes a duplicate block-log row for every block.

A second check walks each interpreter's options up to its first non-option word. It denies an inline-code flag there even when the flag is quoted, as in `python3 "-c" 'print(1)'` or `node '--eval' '...'`. The old hint and the gate both let those through.

Blanking quotes would hide inline code carried in a quoted command string, so the hint now judges that string on its own: a `bash -c "..."` or other shell `-c` argument, an `ssh` last word that holds a space, `eval`'s joined arguments, and each `$(...)` or backtick span. `bash -c "python3 -c 'x'"` and `git commit -m "$(python3 -c 'x')"` stay denied; `git commit -m "Run python3 -c to check"` runs. The interpreter-family lookup moves to `shell_command.interpreter_family`.

An unquoted `-c` after a script file (`python3 tool.py -c x`) stays denied. The gate blocks it anyway, so allowing it in the hint would only swap the hint's advice for the gate's bare block. This is narrower than "judge flags only up to the script argument": it holds for quoted text, not for unquoted script options.

## Evidence

On 2026-10-31 the hint denied a `build_changes.py new` call whose quoted title held the words `git -C`. The call held no inline code and was redone with a reworded title.

## Result

Two allowed cases (a quoted title naming `git -C`, a single-quoted `-e` argument to a node script) and two denied cases (a quoted `-c`, a quoted `--eval`) fail on the old hint and pass on the new one. `python3 -c 'print(1)'`, `python3 -c '...' script.py` and a `-c` run after a script in a later step stay denied.

Median time on a matching call over 21 runs: 21 ms new, 21 ms old, 8 ms for a bare Python start on an empty file.

## Watch

None. The intake counts hook blocks by rule but not false denies, so no number reads this fix.

## Back-out

Revert the commit.
