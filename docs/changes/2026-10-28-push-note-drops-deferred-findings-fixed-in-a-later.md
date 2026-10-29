---
type: "Change"
title: "Push note drops deferred findings fixed in a later round"
description: "The pre-push deferred-findings note leaves out a deferred bug finding when a later round fixed a row at the same session, branch, file and line."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T20:16:04-05:00"}
seq: 212
kind: "fix"
components: ["script/deferred-push-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_deferred_push_check.py::DeferredPushCheckTest::test_finding_fixed_later_at_same_place_is_hidden"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `deferred_push_check.py`: the hook reads every fixed finding row on the repo and branch and drops a deferred row when
  a fixed row has the same session, normalized file and line, a strictly later date, and a different iter when both
  rows carry one. A fix of another finding in the same pass does not count, and rows with no session never match.

## Evidence

- A review loop deferred a finding in one round and fixed it in a later round under a different finding id at the same
  file and line. The hook read only the deferred row and told the session to /fix code that was already fixed.
- The new test fails on the old script: the note still lists the fixed finding.

## Result

- The push note lists only deferred findings that no later round fixed.

## Watch

—

## Back-out

Revert the commit.
