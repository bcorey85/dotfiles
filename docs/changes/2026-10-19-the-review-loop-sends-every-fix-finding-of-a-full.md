---
type: "Change"
title: "The review loop sends every `fix` finding of a full review to a coder at any round"
description: "The review loop sends every `fix` finding of a full review to a coder at any round, and the first fix-diff pass now routes like a full review: every `fix` finding it files gets a coder, blocker or not."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-19T00:00:00-05:00"}
seq: 7
components: ["agent/review-loop", "skill/fix", "agent/code-reviewer"]
evidence: ["work-log reading", "bench reading"]
watches: ["review-loop-fixes-first-pass-findings", "review-loop-fixes-first-pass-findings-escapes"]
---

## Change

The review loop sends every `fix` finding of a full review to a coder at any round, and the first fix-diff pass now routes like a full review: every `fix` finding it files gets a coder, blocker or not. Only two kinds of `fix` finding defer: a non-blocker from the second fix-diff pass, and an open class member at the round cap. The loop ordering block says that the cap stops a reviewer, never a coder. The finding logger takes a `source` field and refuses a deferred `code-reviewer` `fix` row at phase or standalone scope unless the source is the second pass or an open class

## Evidence

work-log reading, bench reading

### Anchor reasons

Anchor `skills/_shared/finding-log.md`, section `## Rules that make the data usable` (evidence: census, judgment):

The field semantics the same two logging commands depend on — which finding counts as one row, what each class means, and when a row is written. The review audit reads the fields on those terms. Every rule the census traced to a consumer stands word for word. Cut by judgment since: the explanatory gloss around them, which the census found has no reader. The `source` field is newer, by work-log reading, same evidence as Step 5c of the review loop: the logger refuses a deferred loop `fix` row unless it came from the second fix-diff pass or an open class at the cap.

## Result

In the work finding log, after the two-round rule, 433 of 1,068 loop `fix` findings deferred, 1.05 per review run against 0.18 before. 61% of them were `docs` findings. Only 14 of 71 branches with a deferred finding got the recap that reads the queue, and 249 deferred findings on the other branches stayed unchanged to the branch tip, 40 of them bug or correctness. In bench loops, 2 of 8 deferred second-round style findings against the written rule. A scratch run of the logger refused the 5 wrong deferrals and a bad source word, and accepted the 7 valid rows. The effect on live runs is unmeasured. Each newly routed finding costs one Sonnet coder, plus one Opus fix-diff pass unless the fix applied only `docs` findings.

## Watch

deferred fix findings per review run (down), review escapes per review run (down).

## Back-out

restore `agents/review-loop.md`, `skills/_shared/finding-log.md` and `skills/review/log-review-finding` from git
