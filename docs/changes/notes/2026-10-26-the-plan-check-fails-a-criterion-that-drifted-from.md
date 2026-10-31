---
type: "Change"
change_type: "changed"
title: "The plan check fails a criterion that drifted from the ticket"
description: "The eng-spec plan check fails a ticket Acceptance line whose text no AC in the criteria file carries and no sign-off names; a ticket with no Acceptance or Requirements heading is skipped."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T11:07:39-05:00"}
seq: 60
kind: "fix"
components: ["skill/eng-spec", "agent/spec-criteria", "script/plan-format"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_finalization_checks.py::AcDriftTest::test_a_reworded_criterion_with_no_sign_off_fails_and_quotes_the_ticket_text"
asked: ""
proof: []
unmeasured: "A reworded criterion that reaches plan review is not logged as its own number."
---

## Change

`code_step.py plan check <spec.md>` now also reads the `00-ticket.md` beside the spec. It fails each ticket Acceptance item whose text, after markdown marks and whitespace are normalised, is the text of no AC in the `acceptance-criteria.md` beside the spec, unless a sign-off line in the criteria file or in the spec's `## Plan Deviations` quotes the item or says `Ticket #<n>`. Order and numbering do not matter. It runs only when both files exist, and a ticket with no `## Acceptance` or `## Requirements` heading is skipped (the reader's `NoCriteriaHeadingError` is caught in the drift check only; verify-prep and verify-log still stop on it). The ticket reader moved from the verify scripts into `plan_format.ticket_criteria`, which verify-prep and verify-log still call through `verify_common`. The spec-criteria agent now copies each ticket criterion verbatim into one AC.

## Evidence

judgment: a plan check passed a plan whose second criterion had drifted from the ticket. Test: the failing test above, with the exact-match, reorder, split, sign-off, missing-criterion and plan-deviation tests beside it. All fail on the base commit, where `ac_drift_failures` does not exist.

## Result

Scoped tests, the full suite and ruff pass.

## Watch

—

## Back-out

Remove `ac_drift_failures` and its call in `spec_ac_failures`, and the paragraph added to the spec-criteria agent.
