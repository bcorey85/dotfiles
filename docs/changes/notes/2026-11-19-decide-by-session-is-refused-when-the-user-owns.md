---
type: "Change"
change_type: "fixed"
title: "decide by session is refused when the user owns the criteria"
description: "`review_fix.py decide adopt|keep --by session` exits with a usage error when no `--plan` is given, the plan cannot be read, or `plan_check.py owner` names the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T02:32:03-06:00"}
seq: 3
kind: "fix"
components: ["script/review-fix", "script/plan-format"]
evidence: ["a-reviewer-question-that-changes-a-criterion-is"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_session_may_not_rule_when_the_user_owns_the_criteria_or_the_plan_is_missing_or_unreadable"
asked: ""
proof: []
unmeasured: ""
---

## Change

`command_decide` reads the criteria owner through `plan_format.plan_criteria_owner` before a session ruling. Owner
`user`, a missing plan or an unreadable plan is refused, and the message says the user must rule with `--by user`.
`DECIDE_BY_NOTE` now says a user's "you decide" is recorded as `--by user`, quoting the instruction.

## Evidence

A session cleared a reviewer question that changed a user-written criterion with its own ruling.

## Result

New tests in `tests/scripts/test_review_fix_script.py`, including the allowed `session` owner case.

## Watch

None.

## Back-out

Revert the commit.
