---
type: "Change"
change_type: "changed"
title: "Coder core bans interpreter code on stdin and programs that write repo files"
description: "The coder's list of shell forms the hooks block now names interpreter code fed on stdin (python3 - <<EOF, python3 <<EOF, cat x | python3) and a program the coder wrote that opens a repo file for writing."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T11:56:42-05:00"}
seq: 74
kind: "user-rule"
components: ["skill/coder-core"]
evidence: ["hook block log"]
watches: []
test: ""
asked: "2026-10-26: The coder brief or coder-core names the interpreter-writes-file form as banned, next to the heredoc ban."
proof: []
unmeasured: ""
---

## Change

- `skills/coder-core/SKILL.md`, "Shell commands the hooks block": the file-write bullet adds "a program you wrote
  that opens a repo file for writing". The inline-interpreter bullet adds interpreter code fed on stdin:
  `python3 - <<EOF`, `python3 <<EOF` and `cat x | python3`.
- `docs/rule-anchors.md`: the block's row carries its new hash and links this change.

## Evidence

On one work branch, coders wrote files through a Bash heredoc in three passes in a day. One heredoc fed a Python
program that rewrote a tracked source module. The shell-write gate does not read a program's own writes. The
inline-interpreter hint now denies every stdin and heredoc interpreter form, subagents included, which is the gate half
of the same queue item. This edit is the brief half, so the coder does not spend a blocked call learning it.

## Result

Text only. The rule-anchors check passes for this block. The hook it describes is pinned by
`tests/scripts/test_inline_interpreter_hint.py::InlineInterpreterHintTest::test_inline_and_stdin_code_is_denied`,
which holds a Python heredoc that writes a file.

## Watch

None. The intake lumps the inline-interpreter hint's blocks into "other Bash hook", so no number reads this edit alone.

## Back-out

Revert the commit.
