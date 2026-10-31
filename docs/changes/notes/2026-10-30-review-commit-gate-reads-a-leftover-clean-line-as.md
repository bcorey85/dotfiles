---
type: "Change"
change_type: "fixed"
title: "Review commit gate reads a leftover clean line as no event"
description: "A session that marked clean before the gate's event format keeps committing after the install, instead of being denied every commit and sent to a review with nothing to read."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T08:01:34-05:00"}
seq: 336
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_a_leftover_clean_line_is_no_event_and_a_plain_dirty_line_still_denies"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_commit_gate.gate_events` skips a plain `clean` line. Before, it read the line as unreadable, so it counted
  as a dirty event at the file's last change.
- A plain `dirty` line and any other unreadable line still read as a dirty event.

## Evidence

- On 2026-10-30 a coordinator session's state file held one `clean` line from three days before the install. Every
  commit that was not a merge conclusion or docs-only was denied, and the deny sent it to a review with nothing new to
  read.

## Result

The new test fails before the change (the commit is denied) and passes after it. `test_review_commit_gate.py` and
ruff pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. Sessions that still hold a leftover `clean` line are denied again until they run a review.
