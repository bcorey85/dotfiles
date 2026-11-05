---
type: "Change"
change_type: "fixed"
title: "refactor log escape rows carry the finding's miss reason"
description: "refactor_flow.py log requires a miss_reason on each escape finding, checks it through log-escape --check before writing, and sends it on the escape row in place of a hard-coded unknown."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T16:40:22-06:00"}
seq: 9
kind: "fix"
components: ["skill/refactor"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_log_escape_row_carries_the_findings_miss_reason"
asked: ""
proof: []
unmeasured: ""
---

## Change

An escape finding in the `log` input carries `miss_reason`. `log` refuses one that is missing, empty, `unknown` or outside the `log-escape` list, and runs each escape row through `log-escape --check` before any row is written, so the list has one owner. The escape row sends the finding's value. `skills/refactor/SKILL.md` names the field.

## Evidence

judgment: a /refactor run logged escape rows with `miss_reason=unknown` because the script hard-coded it, so the escape audit could not tell why review missed them. The new tests fail on f22db22c and pass after.

## Result

`test_refactor_flow.py` passes; full suite 3199 tests, 0 failures.

## Watch

—

## Back-out

Revert the `miss_reason` validation and row field in `refactor_flow.py`, the SKILL.md line, and the tests.
