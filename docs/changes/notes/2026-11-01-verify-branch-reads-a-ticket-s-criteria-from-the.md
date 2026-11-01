---
type: "Change"
change_type: "fixed"
title: "Verify-branch reads a ticket's criteria from the criteria file when the ticket has no Acceptance heading"
description: "/verify-branch on a ticket whose criteria sit under topical headings (B1, B2, ...) now takes them from the plan's acceptance-criteria.md and runs, instead of refusing at prep and spending a human question per branch."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T05:24:28-06:00"}
seq: 445
kind: "fix"
components: ["skill/verify-branch", "script/verify-prep", "script/verify-log"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_a_ticket_with_topical_criteria_headings_takes_its_criteria_from_the_criteria_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `verify_common.branch_ticket_criteria` takes the parsed entries of the task dir's acceptance-criteria.md. When the ticket has no `## Acceptance*` or `## Requirements*` heading, it returns the file's non-manual criteria, each labelled by its id (`AC1`), so the verifier payload, the checklist and the row-coverage check all use them. With no criteria file, or only manual entries in it, prep still refuses; a ticket with an empty or misnamed criteria heading still refuses too.
- verify-prep and verify-log parse the criteria file before the ticket and pass its entries.
- The plan-verifier agent, the verify-branch skill and verify-log's messages name the `ACn` labels beside `Ticket #n`. With `ACn` labels, the plan-verifier also reads each ticket section and gives a `missing` row to any requirement no `ACn` covers, so a criterion the criteria file left out is not dropped.

## Evidence

- Both arms of a bench run stopped at the verify phase on a ticket with topical criteria headings and spent one human question each; the eng-spec criteria file beside the plan already held the criteria.

## Result

- Two new tests (prep payload, and verify-log checklist with rows naming the ids) fail before the change and pass after.

## Watch

None: no intake number counts verify-prep refusals.

## Back-out

Revert the commit.
