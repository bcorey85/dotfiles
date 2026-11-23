---
type: "Change"
change_type: "fixed"
title: "Every logged escape keeps its catch text and file, at every stage"
description: "The escape logger now keeps the catch text of every escape, at every stage, and refuses a row with no description or, outside the plan gate, no file, so each escape can be found and fixed later."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T17:27:21-06:00"}
seq: 36
kind: "fix"
components: ["script/log-escape", "skill/escape"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_log_escape.py::LogEscapeTest::test_every_stage_keeps_its_desc_in_the_text_row"
asked: ""
proof: []
unmeasured: ""
---

## Change

`log-escape` kept the catch text only for hand-catch stages (cc, walkthrough, pr-human, peer-review, prod, other). A PR-bot, refactor, verify, phase-gate, q-verify or plan-review escape lost its text, so nobody could later read what the defect was. It now writes every row, with its text, to the local escape-text file. It refuses a row with an empty `desc=`, and a row with no `file=` unless `gate_missed=eng-spec`. Every known caller already passes both. The escape skill's field notes now say what the logger stores and refuses.

## Evidence

Census of work escapes: 83 high- or medium-severity bug, correctness or security escapes got past code review; 48 were caught by the PR bot and kept no text, 70 carry no miss reason, and 20 have a line number. The user asked on 2026-11-22 that every escape keep enough data to fix it later.

## Result

The named test fails before (only the six hand-catch stages kept text) and passes after. `tests/scripts/test_log_escape.py` and `test_log_escape_check.py`: 53 tests pass. `test_ledger_write.py` and `test_telemetry_switch.py` now pass a description and file to the logger and send its escape-text row outside the test home.

## Watch

None: the intake's escape-text row count shows it once the work machine runs this version.

## Back-out

Revert the commit; older rows are untouched.
