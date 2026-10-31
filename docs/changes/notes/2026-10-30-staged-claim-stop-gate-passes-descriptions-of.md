---
type: "Change"
change_type: "fixed"
title: "Staged-claim stop gate passes descriptions of staging and other sessions' work"
description: "The staged-claim stop gate no longer blocks a reply that describes staging behavior, quotes such words, or reports another session's work, which saves the forced extra turn each block cost."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T10:42:33-05:00"}
seq: 378
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::StagedClaimGateTest::test_a_description_of_staging_behavior_passes_with_an_empty_index"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A `stay` or `remain` claim no longer counts when its clause already says `staged`, so "files you staged stay
  staged" passes.
- A claim no longer counts when its clause names another session, agent, worker or peer, or opens with a possessive
  peer, worker or coordinator ("the coordinator's files"), or when one of them is the whole subject of `left staged`
  ("the worker left staged a list"). The report is about that actor's work. "The worker is staged" still blocks.
- First-person claims ("I staged", "I've staged") skip those two exceptions and go through the review-data rule as
  before, so "the rows I staged are in the ledger" passes.
- Text in double quotes or backticks is dropped before the gate looks for a claim, when it holds a whole claim.
- A claim by this session still blocks, including one beside a description and one that names a worker only as an
  object, such as "the fix to the worker".

## Evidence

The gate blocked two replies with an empty index: one that described what a commit does with staged files, and one
status report that described another session's work.

## Result

Targeted tests pass: descriptions, quotes and reports on other sessions pass, and claims by this session still
block.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
