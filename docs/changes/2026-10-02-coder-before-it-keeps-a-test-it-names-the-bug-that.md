---
type: "Change"
change_type: "changed"
title: "Coder: before it keeps a test, it names the bug that test alone would catch"
description: "Coder: before it keeps a test, it names the bug that test alone would catch, and deletes a duplicate or a test of a mock, the framework or a restated implementation."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 17
kind: "behavior"
components: ["agent/coder"]
evidence: ["census", "judgment"]
watches: []
---

## Change

Coder: before it keeps a test, it names the bug that test alone would catch, and deletes a duplicate or a test of a mock, the framework or a restated implementation

## Evidence

census, judgment

## Result

Work test audits culled 53 tests in 15 audits. In a bench smoke, the coder-only loop wrote half the test lines of the test-writer loop and caught the same 17 of 19 seeded bugs. Effect unmeasured: read culled ÷ `tests_added` from the test-audit log rows.

## Watch

—

## Back-out

restore `skills/coder-core/SKILL.md` from git
