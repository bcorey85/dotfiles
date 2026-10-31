---
type: "Change"
change_type: "changed"
title: "The implement and refactor skills now start the review-and-fix loop's round counter at zero in a first handoff"
description: "The implement skill and the refactor skill now start the round counter of the review-and-fix loop at zero in a first handoff."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-21T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/review-loop", "skill/branch-recap"]
evidence: ["census"]
watches: []
---

## Change

The implement skill and the refactor skill now start the round counter of the review-and-fix loop at zero in a first handoff. Both wrote one. The loop counts a round when it dispatches a reviewer and defers at two, so a start of one left one full review round where the loop's text gives two, and each such run reported a round that it did not run. Every route now gets two full review rounds, then the pass over the fix diff. The ask-outcome log rows of the implement skill and the review skill take the round count that the loop returns, the form that the fix skill already had. Three texts that named a one-round budget, one in the review audit and two in the branch recap, name the round budget without a number. The user chose two rounds over one.

## Evidence

census

## Result

Effect unmeasured. The data came from the work machine, with the rows of both toolkit repositories dropped. The implement skill made 483 of 700 loop starts, and the refactor skill reached the loop in at most 44 more, so the start of one rode on about 7 of 10 loop starts. The earlier row on this counter said that two rounds is what the loop already did in practice. At work that held for the other routes only: of 82 loops with the line counts of both looks, the later look read under half of the first look's lines in 53 and nine tenths or more in 19. The aim is output quality. At work the look after a fix marked 191 findings for repair, and 129 of them went unrepaired to the queue at the end of the branch, 14 of them in the bug or correctness classes. A later look that read the whole diff again marked 0.63 bug or correctness findings for repair per loop against 0.17 for a scoped look, on loops that were denser at the first round, 1.63 against 0.68, so that gap is an upper bound. The price is tokens. By the loop's text, a second full review follows every first review whose repairs a coder made, which is 160 of 231 loops at work, about 7 of 10. The 93 of 231 loops that logged a later look understate it. One more coder run and one more pass over the fix diff follow in about 5 of 10 loops, from the 67 of 93 later looks that marked a repair, and only if the loop repairs what its second review finds. The deferral paragraph of the loop agent reads against its step list on that point. Until that text agrees, the repair is not certain, and with no repair the second review buys a longer queue alone. A census of work transcripts from 2026-08-18 to 2026-09-21, toolkit sessions dropped, gives the price of one dispatch of the diff reviewer on Opus: a median of 59,025 fresh, 679,846 cache-read, and 9,630 output tokens over 537 dispatches, full reviews and passes pooled. On this machine, a guide only, that dispatch costs a median of 22,337 fresh, 122,176 cache-read, and 5,116 output tokens. Back-out watch, from the per-finding log at work: the share of findings marked for repair at the second round that are deferred, baseline 129 of 191; bug or correctness findings marked for repair per loop with a second round, baselines 0.63 and 0.17; deferred findings marked for repair per week, baseline 21.5. Landing check first, from the same log: of loops with a repair at the first round, the share that log a reviewer run at the second round, baseline 78 of 160 and expected near all, and reviewer run rows at the second round or later, baseline 122 of 585. Back out if the second round runs and the deferred share does not fall and the weekly deferred count does not fall. Leave out the rows that a work machine writes between its pull of the loop text and its pull of this edit, because there the first review counts as the second round. Earliest data: work rows and one census table dated after the day on which the work machine pulls the edit, 2026-09-22 at the earliest.

## Watch

—

## Back-out

write one in both handoff lines.
