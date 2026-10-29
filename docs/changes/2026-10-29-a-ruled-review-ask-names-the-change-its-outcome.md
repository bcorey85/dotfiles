---
type: "Change"
change_type: "changed"
title: "A ruled review ask says what its outcome did and names the change"
description: "The ruled-asks line that later reviews and the closing pass read now says what each outcome did to the code and names the change, and puts the phase it was ruled in last, so an ask that offers phases no longer reads as answered by that phase."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T10:49:41-05:00"}
seq: 256
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_open_phase.py::AskOutcomesReachLaterPasses::test_an_accepted_ask_that_offers_phases_reads_as_its_change_made_and_not_as_a_phase"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step_core.record_ruled_asks` keeps the change the ruling names in the `change` key of each ruled ask: the ask's
proposed change for an accepted or rejected ruling, the user's change for a modified one. An ask whose change only
copies its question has no proposal, so it keeps none: an ask with no `change:` marker carries its question as its
change. `ruled_asks_lines` writes `<ask> (<file:line>): <outcome text>: <change> (ruled in Phase N)`:

- accepted: "accepted, so the ask's proposed change is made", with the proposal
- rejected: "rejected, so the ask's proposed change is not made", with the proposal
- modified: "modified, so the user's change is made in place of the ask's proposal", with the user's change

An accepted or rejected ask with no proposal has no change to name, so its line leaves out ": <change>"; a modified ask
still names the user's change. The phase ends the line of a run that has phases; a planless run, or a plan with no
phases, has none, so its line leaves the phase out, where before it read "Phase None". A record written before this
change holds no proposal for an accepted or rejected ruling, so its line leaves out ": <change>" too. Before, the line
was `<ask> (<file:line>): accepted, Phase 0`, with no change named.

## Evidence

Judgment from one bench run. A review ask asked whether a code comment lands in Phase 0, as the plan says, or in Phase
10, when it becomes true. The session accepted the ask, and the coder moved the comment. The next review read the line
"...: accepted, Phase 0" as the answer "Phase 0", flagged the coder's change as plan drift and asked to undo it. The
session spent a plan-impact decision, an extra coder run and an extra review round to get back to its own ruling.

## Result

The named test fails before the change (the line read "accepted, Phase 2") and passes after it. Two tests beside it
pin an ask whose change only copies its question (no change printed) and an accepted record from before the change
(no change printed). Two more give the ask its own proposal: a modified ask names the user's change and not that
proposal, and a rejected ask names the proposal it turned down. One more pins the outcome texts to the outcome words
`review_asks.ASK_OUTCOMES` accepts, so a new outcome word fails the suite instead of a ruled-asks line. The code_step
test files pass.

## Watch

None: no intake row counts a ruled ask that a later review raises again.

## Back-out

Revert the commit. The old line code reads the same keys, so a `ruled-asks.json` written after this change still loads.
It would print the proposal kept for an accepted or rejected ask as "the user's change", so delete that file when
backing out in the middle of a run.
