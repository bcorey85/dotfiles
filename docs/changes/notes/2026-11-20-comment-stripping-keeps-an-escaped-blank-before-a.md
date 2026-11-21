---
type: "Change"
change_type: "fixed"
title: "Comment stripping keeps an escaped blank before a hash"
description: "A # after a backslash-escaped blank is part of its word, so strip_comments no longer cuts the rest of the line as a comment."
generated: {"by": "claude-sonnet-5-5/coder", "at": "2026-11-20T20:41:57-06:00"}
seq: 4
kind: "fix"
components: ["script/shell-write-gate", "script/shell-quoting", "script/shell-statements"]
evidence: ["review of the shell gates: echo x\\ #; echo hi > tracked.txt hid the write behind a comment the shell never starts"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_an_escaped_blank_before_a_hash_does_not_start_a_comment"
asked: ""
proof: []
unmeasured: ""
---

## Change

`strip_comments` moved into `lib/shell_quoting.py` and shares `starts_comment` with the quote scan. A `#` right after a character the backslash hid (`x\ #`) starts no comment in either, so the text after it stays visible to the gates. A `#` after a backslash-newline is judged by the text before the backslash, as the shell joins the lines first: `echo a \` newline `#it's fine` holds a comment, so its quote opens no quote.

## Evidence

`echo x\ #; echo hi > tracked.txt` was allowed before and is denied now; `StripCommentsTest.test_a_hash_after_an_escaped_blank_starts_no_comment` pins the reader.

## Result

The 12002-command replay of real Bash commands (see the computed-target note) was run over the final tree; its verdict changes are listed there.

## Watch

A command with a backslash-escaped blank before a `#` that is denied for text the user meant as a comment. Each one is the case to review.

## Back-out

Remove the `_follows_hidden_character` call from `_QuoteScan._read_unquoted` in `lib/shell_quoting.py`; `strip_comments` follows it through the scan. `shell_statements.clean` blanks its comments through the same `strip_comments` scan, so it follows the removal too.
