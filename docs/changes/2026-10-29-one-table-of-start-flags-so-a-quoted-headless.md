---
type: "Change"
title: "One table of start flags, so a quoted --headless start splits"
description: "The /code start flags now come from one table in code_step_start_args.py; a start string that opens with --headless is split into words instead of exiting on an unknown flag."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T09:38:38-05:00"}
seq: 250
kind: "fix"
components: ["skill/code"]
evidence: ["code review"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartArgsTest::test_each_switch_and_task_file_in_one_quoted_argument_splits_into_its_words"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step_start_args.py` defines `TASK_FLAG`, `VALUE_FLAGS`, `SWITCH_FLAGS` and `START_MODIFIERS`, and
`START_FLAGS` joins them. The check that splits one quoted argument uses `START_FLAGS`; the old list of leading
flag words, which lacked `--headless`, is gone. The flag-end scan uses `VALUE_FLAGS`, and the unknown-flag check in
`code_step_start.py` uses `SWITCH_FLAGS`; `parse_start_args` reads `TASK_FLAG` and `VALUE_FLAGS`.

## Evidence

A code review found the start flags written out in several places, one of which lacked `--headless`. So
`start "--headless --task fix the totals"` was not split and exited 2 on an unknown flag. The test also checks a quoted `--task-file <path>`
start, which split before only because `--task` is a prefix of `--task-file`.

## Result

The new test fails before the change (exit 2 on the `--headless` row) and passes after it.

## Watch

None; a fix with a test.

## Back-out

Revert the two script files and the test.
