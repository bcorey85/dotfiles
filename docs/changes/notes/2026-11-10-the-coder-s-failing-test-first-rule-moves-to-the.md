---
type: "Change"
change_type: "changed"
title: "The coder's failing-test-first rule moves to the top of its rule list"
description: "The coder's failing-test-first line now sits first in its first rule list, so the coder writes and runs a failing test before a small frontend fix where it used to skip the test."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-10T19:17:15-06:00"}
seq: 6
kind: "structured"
components: ["skill/coder-core"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-10-moving-the-failing-test-first-rule-to-the-top-of"]
unmeasured: "No intake number reads the order of a coder's test and source edits on a bug fix. Measured on React and a TypeScript backend with the line at the top; Vue and Django held with the line in its old place and were not rerun."
---

## Change

`skills/coder-core/SKILL.md`: the line "For a bug fix, do not edit the source file until a new test has run and
failed. Write the test, run it, quote the failing line, then fix." moved from the end of the tests section to the
first bullet of the first rule list. The wording is unchanged.

## Evidence

rule meter: a Sonnet coder with a plain task prompt on a one-character React bug fix, graded by a script on the
order of its tool calls.

## Result

Runs where a test edit and a test run came before the first source edit, 8 runs per cell:

| Where the line sits | React | TypeScript backend |
|---|---|---|
| No line | 0/8 | 0/8 |
| Old place, end of the tests section | 3/8 | 7/8 |
| First bullet of the first rule list, test copy of the file | 8/8 | 8/8 |
| First bullet of the first rule list, copy of the file as it ships | 8/8 | no run |

In the misses the coder made the fix without opening the test file. `bash tests/run.sh` passes.

## Watch

None: see `unmeasured`.

## Back-out

Move the line back to the end of the tests section in `skills/coder-core/SKILL.md` and restore the two anchor rows.
