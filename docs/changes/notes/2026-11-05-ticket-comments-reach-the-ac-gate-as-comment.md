---
type: "Change"
change_type: "fixed"
title: "Ticket comments reach the AC gate as Comment labels"
description: "verify-prep lists each ticket comment as a `Comment #n` label in the plan-verifier dispatch, verify-log requires a row for each, and /verify-branch refreshes the snapshot's comments first, so a criterion added only in a comment is verdicted."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T16:49:36-06:00"}
seq: 11
kind: "fix"
components: ["script/verify-prep", "script/verify-log", "agent/plan-verifier", "skill/verify-branch", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::TicketCommentTest::test_the_verifier_payload_lists_each_comment_after_the_ticket_criteria"
asked: ""
proof: []
unmeasured: ""
---

## Change

`plan_format.ticket_comments` reads a `## Comments` section (one `###` heading per comment; no sub-heading means one comment; `none` means none) or a `Comments:` field line, and fails loudly on text before the first comment heading. verify-prep appends the `Comment #n` entries to `ticketLabels` and `ticketLines`. verify-log adds the `no-criterion` verdict, accepted only on a `Comment #n` row and not a gap. plan-verifier verdicts a comment that adds or changes a criterion like a ticket AC, else `no-criterion`. /verify-branch step 0 refetches the ticket and rewrites the `## Comments` section; jira-ticket.md says how comments are persisted. The opencode plan-verifier copy is an older text without the label rules and is skipped.

## Evidence

judgment: a work snapshot recorded `Comments: none` at plan time; later comments added criteria, and the verifier saw them only because the criteria file had folded them in by hand. All six new tests fail on the base commit and pass after. The one local real ticket parses (parsed 1 of 1, no comments).

## Result

`test_verify_branch_script.py` 142 pass; lint clean; rule anchors check clean.

## Watch

—

## Back-out

Remove `ticket_comments` and its helpers, `branch_ticket_comments`, the verify-prep label merge, `NO_CRITERION`, and the prompt lines.
