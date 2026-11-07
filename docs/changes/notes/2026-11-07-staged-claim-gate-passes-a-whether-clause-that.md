---
type: "Change"
change_type: "fixed"
title: "Staged-claim gate passes a whether-clause that describes staging"
description: "The staged-claim Stop gate reads `whether` as a conditional word, so a reply that describes staging as a mechanism (\"the same hash whether it is staged or untracked\") no longer blocks the stop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T02:50:45-06:00"}
seq: 7
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::StagedClaimGateTest::test_a_whether_clause_describes_staging_and_passes_with_an_empty_index"
asked: ""
proof: []
unmeasured: ""
---

## Change

`gates/staged_claim_gate.py` adds `whether` to its conditional words. A `whether` ahead of the claim in its own clause makes the clause hypothetical, as `if` does. A `whether` in an earlier clause still leaves a later claim blocked.

## Evidence

judgment: a session explaining a commit-gate fix wrote "the fingerprint will hash a new file the same way whether it is staged or untracked". The gate read `is staged` as a claim about the cwd index, found it empty, and blocked the stop four times in a row. The new test fails before the change and passes after.

## Result

Staged-claim gate tests pass (58). Gate median 34 ms over 15 runs against a bare Python start of 8 ms; the change adds one word to an existing regex.

## Watch

—

## Back-out

Remove `whether` from `CONDITIONAL` in `gates/staged_claim_gate.py` and the two new tests in `tests/scripts/test_staged_claim_gate.py`.
