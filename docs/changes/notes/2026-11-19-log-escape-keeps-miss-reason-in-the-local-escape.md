---
type: "Change"
change_type: "fixed"
title: "log-escape keeps miss_reason in the local escape text for every stage"
description: "log-escape writes a local escape-text row for every row with a miss_reason, any stage, and its note names that file when the ledger refuses the field."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T12:55:21-06:00"}
seq: 9
kind: "fix"
components: ["script/log-escape", "script/log-escape-check", "script/ledger-write", "skill/escape"]
evidence: ["log-escape-drops-the-miss-reason-that-cc-asks-for", "log-escape-drops-miss-reason-that-escape-ratchet"]
watches: []
test: "tests/scripts/test_log_escape.py::LogEscapeTest::test_a_ledger_that_refuses_miss_reason_leaves_it_in_the_text_file_and_the_note_names_the_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

`telemetry/log-escape` writes the miss_reason through `ledger-write --local escape_text` for every stage, with or without a desc. When the ledger refuses the field, the note says the row was logged without it and names the local file (`ledger-write --local-path`). `log-escape-check` matches the new note and checks the file.

## Evidence

The installed ledger refuses `miss_reason`; log-escape resent the row without it, and escape-text.jsonl kept rows only for hand-catch stages with a desc, so the label was lost.

## Result

New tests in `test_log_escape.py` and `test_ledger_write.py`.

## Watch

None.

## Back-out

Revert the commit.
