---
type: "Change"
change_type: "fixed"
title: "Criteria owner reads every queue Source line, so a human item named second keeps the user as owner"
description: "A lane ticket that names a session-written queue item before a human-written one now reads as user-owned, so a session can no longer rule on the user's criteria; every queue Source line is now checked, not only the first."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T00:51:38-06:00"}
seq: 2
kind: "fix"
components: ["script/plan-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_format.py::CriteriaOwnerTest::test_a_human_item_named_after_a_session_item_keeps_the_user_as_owner"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/plan_format.py`: `queue_source_line` becomes `queue_source_lines` and returns every queue `Source:` line.
`criteria_owner` hands them to the new `queue_sources_owner`, which checks every line's queue item first. It returns
`user`, with that line as `source`, when any item has a `human:` author, and otherwise `session` with the first line.

## Evidence

Judgment from reading the code: a lane ticket writes one `Source:` line per queue item it carries, and the reader
stopped at the first. 34 queue items are human-written.

## Result

The two new tests fail before the change and pass after it: a human item named second keeps the owner `user`, and a
later line that names a missing item raises. `test_plan_format` and `test_verify_prep_queue_ticket` pass on a copy of
the toolkit with the change.

## Watch

None: a fix with a failing-before test.

## Back-out

`git revert` the commit.
