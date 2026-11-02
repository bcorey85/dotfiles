---
type: "Change"
change_type: "fixed"
title: "A ledger refusal or failure never stops log-escape"
description: "A row the ledger refuses or fails on now lands in the local jsonl with one stderr note and exit 0. log-escape checks its own required fields, so a bad call still exits 1."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T21:30:54-06:00"}
seq: 462
kind: "fix"
components: ["script/log-escape", "script/ledger-write"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_log_escape.py::test_a_ledger_failure_keeps_the_row_locally_with_one_note_and_exit_0"
asked: ""
proof: []
unmeasured: ""
---

## Change

`ledger-write --local <type>` skips the ledger and appends the row to its local file. `log-escape` uses it when `ledger write` exits non-zero: the row is kept, one stderr note gives the exit code and the ledger's words, and it exits 0. `gate_missed`, `stage_found` and `class` are now checked in `log-escape` with exit 1, where the ledger's exit 2 did that job before.

## Evidence

The ledger can never block dotfiles or the workflow. A refused or failed write used to pass its exit code to the caller and lose the row.

## Result

`tests/scripts/test_log_escape.py` covers exits 1, 2 and 75, a refusal of another field, a refusal after the miss_reason retry, and each required field refused before the ledger. `log-escape-check` passes on the installed ledger.

## Watch

None. Rows kept this way sit in `~/.claude/review-escapes.jsonl` until a ledger reads them.

## Back-out

Revert the commit.
