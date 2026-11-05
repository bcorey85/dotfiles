---
type: "Change"
change_type: "fixed"
title: "Deferred-findings push notice says fixes before the first commit do not show"
description: "deferred_push_check.py says that a fix made before the branch's first commit does not show in its list, and tells the reader to fix each finding still open."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T01:35:49-06:00"}
seq: 4
kind: "fix"
components: ["script/deferred-push-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_deferred_push_check.py::DeferredPushCheckTest::test_the_notice_says_a_fix_made_before_the_first_commit_does_not_show"
asked: ""
proof: []
unmeasured: ""
---

## Change

The header now ends with `UNCHANGED_SCOPE`: a fix made before the first commit does not show here, so read each line before acting. `CLOSING_LINE` says to fix each one still open with /fix.

## Evidence

judgment: a session took the push notice's list as open bugs and refixed findings already fixed before the first commit. Finding rows are logged on uncommitted code against the first commit, so the check cannot see such a fix without storing reviewed content. The new test fails on the base commit and passes after. Hook median on a push event: 32.4 ms, next to 7.6 ms for a bare Python start (20 runs each; the change is text only).

## Result

`test_deferred_push_check.py` 16 of 16 pass; lint clean.

## Watch

—

## Back-out

Restore the old header and `CLOSING_LINE`, remove `UNCHANGED_SCOPE` and the new test.
