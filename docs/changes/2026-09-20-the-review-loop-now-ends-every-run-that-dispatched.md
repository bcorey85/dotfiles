---
type: "Change"
change_type: "changed"
title: "The review loop now ends every run that dispatched a fix coder with a reviewer, never with a coder"
description: "The review loop now ends every run that dispatched a fix coder with a reviewer, never with a coder."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 10
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["census", "judgment"]
watches: []
---

## Change

The review loop now ends every run that dispatched a fix coder with a reviewer, never with a coder. The pass over the fix diff is owed before a deferred return, and the deferral no longer declares the loop over. The pass runs at most twice, so a repair made under the blocker carve-out is read as well. The second pass dispatches nothing: a blocker returns a critical-blocker status, and everything else defers. The dispatch is built from the fix coder's own reported file list and its optional line ranges, with no git call. The step heading, the ordering block, and the re-entry line now state the same bound. The opencode copy took the same changes.

## Evidence

census, judgment

### Anchor reasons

Anchor `agents/review-loop.md`, section `## Step 5d: Fix-diff verification (once per unread fix diff)` (evidence: removal round; census, judgment):

One reviewer pass over every fix diff that is unread when the loop returns, outside the caps, once per unread fix diff. The trimmed arm of the removal round dropped two rationale sentences. The pass followed every coder in the full arm, 5 of 5, and 5 of 6 in the trimmed arm, which once returned deferred with the fix diff unread. The bound, the heading, and the dispatch contract changed after a census of live runs. The pass ran in 2 of the 5 live loops with a fix coder, and in both of those a further fix followed it, so the old single pass left a repair with no reader. The contract drops the diff text because 9 pass dispatches carried it 0 times, while a bare git call with no revision range preceded 8 of those 9. The bound is now the fix diffs the pass has not read, not a count of two, because 4 of the 5 live loops with a fix coder ended on a repair ordered by a specialist reviewer that no one read. Only the first pass routes, and every later one dispatches nothing. The rule that the last dispatch of a loop with a fix coder is a reviewer stands, and it is conditional on the `no-review` flag, which returns converged with no reviewer after a fix coder ran. The heading now states the bound only, and the ordering line states the rule without that condition, because that flag returns before the loop is entered. The definition of a read diff is newer, by judgment: a fix diff counts as read once a pass read it, or once a later full review of the same loop had all of its files in scope, so a clean second review that covered the first repair gets no pass. Every other fix diff is unread, a repair that a specialist ordered included, so a specialist's own second look is no reading. In a census of work transcripts a later pass read 13 of 74 specialist-driven repairs. No run shows the definition. The effect of the change is unmeasured. A docs-only fix diff counts as read: census, same evidence as the docs-only exit in Step 5. The specialist counter and the clause on a repair that a specialist ordered are gone with the specialist pass. The first pass now routes like a full review: every `fix` finding it files gets a coder, blocker or not, and the second pass reads that diff unless it applied only `docs` findings. Work-log reading, same evidence as Step 5c.

## Result

Unmeasured. A fix coder ran in 5 of 15 live loops, and the pass ran in 2 of those 5. In all 5 the last dispatch was the coder with nothing behind it, so no reviewer read the final fix diff. In both runs that did run the pass, a further fix followed it. The prompt carried the fix diff in 0 of 9 pass dispatches, and a bare git call with no revision range preceded 8 of those 9. One pass costs about 160,000 tokens on the largest model at the median, of which about 142,000 are cache reads. Live checks: the share of loops with a fix coder whose last dispatch is a reviewer, now 0 of 5, the count of second passes, the count of critical-blocker returns from a second pass, and the share of pass dispatches that name the coder's file list, now 2 of 9.

## Watch

—

## Back-out

—
