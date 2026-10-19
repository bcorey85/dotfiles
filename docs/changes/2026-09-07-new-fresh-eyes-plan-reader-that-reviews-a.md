---
type: "Change"
title: "New fresh-eyes plan reader that reviews a finalized plan before any coder runs — given the plan"
description: "New fresh-eyes plan reader that reviews a finalized plan before any coder runs — given the plan, ticket and acceptance criteria by path and nothing from the conversation that produced them — reporting dangling dependencies, contracts that disagree between phases, ticket requirements no phase owns."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-07T00:00:00-05:00"}
seq: 2
components: ["agent/plan-reviewer"]
evidence: ["escape ranking + judgment"]
watches: []
---

## Change

New fresh-eyes plan reader that reviews a finalized plan before any coder runs — given the plan, ticket and acceptance criteria by path and nothing from the conversation that produced them — reporting dangling dependencies, contracts that disagree between phases, ticket requirements no phase owns, instructions with two readings, criteria that cannot fail, and an approach that either cannot work or is not the one to take — arguing the shape of the design, not only its executability, and rubber-ducking each phase back in a line; re-dispatched fresh until it returns clean, capped at three rounds, its real findings logged to the escape file at a new earliest-possible stage so they cross-tabulate with the plan defects that did escape, with its finding and round counts added to the planning-lane row. Pinned to the larger model, with no smaller tier. Both planning-budget ceilings raised with sign-off to admit it, and the planning-lane log row moved out of finalization into the new phase so the row records what the review cost and returned

## Evidence

escape ranking + judgment

## Result

The planning lane is the largest source of high-severity defects that reach a downstream stage, and effectively all of them are the plan and the code disagreeing — which no reviewer of the diff can catch, because a wrong plan and a faithful diff agree with each other. Every check the lane already runs is performed by the session that wrote the plan: they ask whether its commands run and whether its claims about the tree hold, never whether the document is executable by someone who was not in the room. Trial reads of a finalized plan from a cleared context returned several distinct defects every time, including on repeat reads of the same plan, which is why the loop re-dispatches fresh rather than continuing the same reader. Same fresh-eyes principle already load-bearing for structure review, applied one lane earlier. Pinned to the larger model because this is the one review whose misses cannot be recovered downstream — a defect in the plan reaches every phase built on it, and the reviewers that run later check the code against that plan, so they agree with the defect rather than catching it. Its findings are also the kind that come from holding a whole document in view at once (a literal frozen in one phase and contradicted in another, a requirement no phase owns), which is where the tiers separate most. No smaller tier exists; a cheap read here buys nothing. The design is fully in scope, including approaches that work. A finalized plan is one way to satisfy the ticket found in a single pass — the first path that survived contact, not a search over the alternatives — and nothing downstream ever argues with it again, because every later gate checks the code against it. This reader is the only adversary the design gets, so it attacks the shape as well as the executability: phases that disappear under a different decomposition, work the tree already does, choices cheap now and expensive at the next change the ticket implies. A settled decision records what was chosen, not that alternatives were searched, so it is arguable too; the ticket owner still decides, and both an accepted and a declined alternative become decision entries. Guarded against noise by a bar every alternative must clear — what changes, what disappears, what it costs, and why the authors would not have seen it — because an unargued suggestion spends the attention the real findings need. Alternatives are counted separately from defects and are never filed as escapes: the plan was correct, no gate missed anything, and mixing them would make the lane's defect count unreadable. Raised-versus-accepted is the pair that says whether arguing the design pays.

## Watch

—

## Back-out

—
