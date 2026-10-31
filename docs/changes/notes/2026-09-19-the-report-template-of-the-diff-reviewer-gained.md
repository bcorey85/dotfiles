---
type: "Change"
change_type: "changed"
title: "The report template of the diff reviewer gained two lines (67 words, 588 in the agent file)"
description: "The report template of the diff reviewer gained two lines (67 words, 588 in the agent file)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-19T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["seeded round", "census"]
watches: []
---

## Change

The report template of the diff reviewer gained two lines (67 words, 588 in the agent file). Under the fix heading: the blocker tag only when the item means data loss, a security breach, or a production outage in normal use, and anything less is a plain fix. Under the ask heading: only two cases are a question, a premise that the reviewer checked and cannot confirm, or a real defect with more than one defensible correction, and the reviewer finishes every check that it can run. The opencode copy has no patch, because it keeps the full text with the pointer to the shared judgment text, which already defines both rules. The deep variant reads the base file, so it inherits the lines.

## Evidence

seeded round, census

### Anchor reasons

Anchor `agents/code-reviewer.md`, section `## Output Format` (evidence: removal round, seeded round, judgment):

The report template the dispatcher parses: summary headings, prior issues, Fix/Ask/Nit. Kept verbatim in the contract-only text that matched the full prompt in two replicates at opus, plus one sentence added by judgment: the plan-impact prefix that the review loop scans for. That prefix used to live in the removed disposition text, and no bench exercises it. Two lines came in after a seeded round: the definition of the blocker tag, and the two-case limit on questions. On frozen reviews they took the blocker tags to none and the reviews with a question from more than half to a third, at equal tokens, with every planted regression still named.

## Result

In the work logs, the share of diff reviews that stop for the user about doubled after the reviewer lost its pointer to the shared judgment text, and the share with a blocker tag rose about five times. On frozen trees with planted regressions, the live text with the two lines gave a question in a third of the reviews, against more than half for the live text alone, and it used no blocker tag, against several. Every question that asked a human to confirm a premise or an intent went away, and none of them named a defect. Every planted regression was still named, no fix item was false or outside the diff, the count of real defects was level, and the tokens of a review were level in each type: fresh, cache read, and output. The gain is human attention, about two fewer stops in ten reviews, and no repair forced past the round budget by a tag used for emphasis. The cost is 67 always-loaded words in each diff review. One quality fact goes with it. On the one tree where the live text sides with the code against the written spec, the review without the lines still put one question about the change to a human, and the review with the lines asked nothing. The root error is in both texts, so the lines did not cause it, and a fence for that case is not tested yet. Limits: the lines ran in one block with two other lines that stay out, a fix label for small real defects and a cap on advisory items, because the frozen reviews hold no small real defect in the advisory tier to score them. The reference reviews were one day older than the new ones.

## Watch

—

## Back-out

—
