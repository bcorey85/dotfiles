---
type: "Change"
change_type: "fixed"
title: "Staged-claim gate passes a line that names a check of what is staged"
description: "A reply that describes a check against what is staged no longer reads as a claim that the index holds files, so the Stop hook stops sending it back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T18:40:00-06:00"}
seq: 9
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["queue: staged-claim-stop-gate-fires-on-a-line-that-names"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::StagedClaimGateTest::test_a_check_of_what_is_staged_passes_with_an_empty_index"
asked: ""
proof: []
unmeasured: "A Stop-hook false positive with no logged rate; each hit cost a turn spent on git diff --cached."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `gates/staged_claim_gate.py`: an `is staged` or `are staged` claim with `what`, `whatever` or `whichever` right before it is no index claim.
- A copula before `what` (`Here is what is staged: …`, `This is what is staged`) keeps it a claim.
- First-person (`what I staged`) and past-tense (`what was staged`) forms still count as claims.
- A new test pins that a claim naming another worktree's file by path is checked against that worktree's index.

## Evidence

"It checks the skill list against what is staged." was blocked twice in one session with an empty index.

## Result

The new tests fail before the change and pass after. "I staged the change." still blocks with an empty index.

## Watch

None.

## Back-out

Revert the commit.
