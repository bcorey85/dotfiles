---
type: "Change"
title: "/code passes the user's ruling on a plan disagreement to the review, so the review stops asking it again"
description: "When the code and the plan disagree, /code records the user's answer, in their words, as a ruling. The review after it gets the ruling as a RESOLVED block and reviews the code against it. Before, the review raised the same disagreement again after the user answered, and a work run looped."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-19T12:08:53-05:00"}
seq: 9
components: ["script/code-step", "agent/review-loop", "shared/handoff-block"]
evidence: ["work incident"]
watches: []
---

## Change

`code-step.py decide <adopt|keep|discuss>` takes `--ruling "<the user's words>"`. The script stores the decision, who ruled, when, and the words. The plan deviation entry quotes the words and the disagreement it settles. The handoff to the next review carries a `plan_impact` block that starts `RESOLVED`. A pre-set decision records "no user was asked" as its ruling.

`agents/review-loop.md` Step 1: a handoff `plan_impact` that starts `RESOLVED` is the user's ruling. The loop passes it to every reviewer as the standard, and returns `plan-impact` only for a disagreement the ruling does not settle.

`skills/_shared/handoff-block.md`: the `plan_impact` field is `none` or a `RESOLVED` block, and the consumer rules say to review against the ruling.

The edit came in from the work machine in one commit with unrelated terminal scripts.

## Evidence

work incident

### Anchor reasons

Anchor `agents/review-loop.md`, section `## Step 1: Parse args` (evidence: work incident): a `RESOLVED` plan_impact is the user's ruling, so the loop reviews against it and does not return it as a question.

Anchor `skills/_shared/handoff-block.md`, section `## Canonical schema` (evidence: work incident): the `plan_impact` field carries the ruling, who ruled, when, and the user's words.

Anchor `skills/_shared/handoff-block.md`, section `## Consumer rules` (evidence: work incident): a `RESOLVED` block is settled, so a consumer never returns it as `plan-impact`.

## Result

A work run of `/code` looped: the user answered a plan disagreement, and the next review raised it again, so the router asked again. The fix stops the review from returning a settled disagreement.

The dotfiles script tests were written for the old `decide` form. They now use `decide --ruling`, and 3 new tests cover the ruling: its words reach the plan deviation, the next review gets the `RESOLVED` block, and a `decide` with no ruling stops and changes nothing.

A new test walks every router path from every verb and fails on a repeated step. On the router before the fix it finds 18 loops, each one the answered plan question asked again. On the fixed router it finds none in about 186,000 paths. The full dotfiles script suite passes, 80 of 80.

## Watch

None. The work logs record no count of repeated plan questions per run. The path-walk test in the dotfiles CI guards the fix.

## Back-out

Revert the `code-step.py`, `review-loop.md` and `handoff-block.md` hunks of dotfiles commit `88b5f73d`.
