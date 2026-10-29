---
type: "Change"
change_type: "fixed"
title: "verify-log refuses a run with no verdict row for a ticket criterion"
description: "verify-log checked that every acceptance-criteria.md id had a verdict row, but never checked the ticket's own criteria. A ticket-only run, or a task dir with no criteria file, logged CLEAN with any non-empty rows. verify-prep now saves the ticket criterion labels, and verify-log exits 2 and writes nothing when a `Ticket #n` has no row."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T23:35:21-05:00"}
seq: 21
kind: "fix"
components: ["script/verify-log", "script/verify-prep", "agent/plan-verifier", "skill/verify-branch"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::TicketOnlyLogTest::test_rows_that_skip_a_ticket_criterion_exit_2_and_write_nothing"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `verify-prep` saves `ticketLabels` (`Ticket #1`, `Ticket #2`, ...) in the context, in the order `verify_common.ticket_criteria` numbers them.
- `verify-prep` prints each `Ticket #n: <criterion>` in the plan-verifier dispatch, so the verifier uses the same numbering as the check.
- `verify-log` exits 2 and writes nothing when a label has no row whose `item` starts with it. The match ends at a word boundary, so `Ticket #1` does not match `Ticket #12`, and a label cited mid-row does not count. The check runs in every mode, with or without `acceptance-criteria.md`. `--result NA` skips it.
- The plan-verifier starts each row with a label from the dispatch. The verify-branch skill says that a row is needed for every listed label.

## Evidence

A census of the agent-read toolkit scripts looked for checks that pass when their data is absent. This was the worst one found. The branch-completeness verdict checked only the criteria-file ids. The ticket ACs are the contract, and the script never checked that each one got a verdict.

## Result

Before the fix, the three refusal tests fail against the live scripts. After it, `test_verify_branch_script` runs 107 tests and passes. The guards for the clean path and the NA skip pass before and after.

## Watch

None. A refusal is an exit 2 in the session, and no intake stream counts verify-log exits.

## Back-out

Revert the edits to `verify-prep`, `verify-log`, `plan-verifier.md` and the verify-branch skill. Ticket criteria then go unchecked again.
