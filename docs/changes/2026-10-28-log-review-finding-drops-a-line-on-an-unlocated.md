---
type: "Change"
change_type: "fixed"
title: "log-review-finding drops a line on an unlocated finding and logs it"
description: "log-review-finding exited on `file=unlocated` with a `line=` and logged no row; it now drops the line with a warning on stderr and logs the row with no file and no line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T11:04:42-05:00"}
seq: 182
kind: "fix"
components: ["script/log-review-finding"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_log_review_finding.py::TestAuditRowTest::test_an_unlocated_finding_with_a_line_is_sent_without_the_line_and_warns"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `file=unlocated` with a `line=` no longer exits. The script prints `line=<n> dropped` on stderr and sends the row
  with no file and no line.

## Evidence

- A review loop logged an unlocated finding with a line. The script refused it, so the finding row was lost until the
  agent noticed and retried.

## Result

- The finding row is logged on the first call.

## Watch

—

## Back-out

Revert the commit.
