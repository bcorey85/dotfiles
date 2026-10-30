---
type: "Change"
change_type: "changed"
title: "The review loop now gives the fix coder the advisory items of the same review pass"
description: "The review loop now gives the fix coder the advisory items of the same review pass, in a `## Small items` section below the fix findings, under a fixed instruction text (64 words)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/review-loop", "skill/branch-recap"]
evidence: ["seeded round", "census", "judgment"]
watches: []
proof: ["2026-09-20-loopnit-1"]
impact: {"metric": "quality", "before": 4, "after": 1, "unit": "real small defects left uncorrected (of 4)", "finding": "2026-09-20-loopnit-1", "better": "lower"}
---

## Change

The review loop now gives the fix coder the advisory items of the same review pass, in a `## Small items` section below the fix findings, under a fixed instruction text (64 words): apply an item only when it names wrong behavior or a false statement in a doc or a comment and one correction is clear, skip and report every other item, and never widen the change. An advisory item still never causes a dispatch. A repair that no reviewer reads afterwards carries no small items. An applied item stays in `nit[]` with the ending `applied`, never moves to `fixed[]`, and logs as fixed in its per-finding row. A skipped item ends in `skipped` with its reason. The Step 5 heading changed with it. The agent file grew by about 185 words. The opencode copy has the same patch. The reviewer texts that call an advisory item never fixed stay unchanged on purpose. One caller changed: the branch recap lists only the advisory lines that do not end in `applied`. The other callers render the lines inline and need no change.

## Evidence

seeded round, census, judgment

### Anchor reasons

Anchor `agents/review-loop.md`, section `## Step 4: Classify the reviewer output` (evidence: removal round, seeded round, judgment, census):

Route each finding on the label the reviewer gave it, never re-label, and the plan-impact and perf rules. The trimmed arm dropped the plan-impact definition and stopped for a plan decision in one run where the full text stopped in five. It sent a coder after the same judgment calls at 20% more loop tokens at the median. The definition is the likely routing text, untested alone. The advisory line changed after a seeded round: when the pass sends a fix coder, the advisory items ride along, and they never cause a dispatch. With them, a live coder corrected 3 of 4 real small defects against 0 without them, on five saved trees, with no worse tree and no change outside the items. The loop's own obedience to the changed line is unproven: the test rig built the coder prompt. The `fix` bullet no longer says that a fix counts toward the round counter, because a round is counted where a reviewer is dispatched. That cut is by judgment. The query-cost paragraph is gone with the query-cost reviewer. Census of work logs: the security and query-cost reviewers fixed 0 findings in 53 runs. By judgment, a finding marked as a design decision joins the questions for the user, whatever its disposition. The structure format promises that the loop sends such a finding to the user.

Anchor `agents/review-loop.md`, section `## Step 5: Fix dispatch (only a `fix` finding dispatches)` (evidence: removal round, seeded round, census, judgment, bench smoke):

One fresh coder with the fix findings for each round, with no deep variant since the coder pins Opus, the verbatim fence, and the coder-report post-processing. The trimmed arm dropped three asides. Coder dispatches were 9 against 8 over twelve runs per arm, with no fix outside a coder in either arm. Added after a seeded round: the small-items section and its instruction text, word for word as tested. With that section, a live coder corrected 3 of 4 real small defects against 0, all three in docs. It skipped the one behavior item with a reason, broke no fix check and no guard check, and cost 2% more coder tokens at the median. Five trees bound the rate of a harmful change only below 45%. Added by judgment, then traced by a census of consumers: no small items on a repair that no reviewer reads afterwards, the ban on a dispatch for advisory items alone, and the bookkeeping that keeps an applied small item out of `fixed[]` and logs it as fixed in the per-finding row. The fence and the small-items text are passed to the coder word for word, `fixed[]` is what the three wrapper skills render under Fixed, and the per-finding row is read by the finding-log script and the review audit. The reviewer texts that say an advisory item is never fixed stay unchanged on purpose: a changed line under the reviewer's advisory heading lost verified defects before, and the tested reviews were written under the present text. The closing sentence is newer: the step builds `prior-issues` from the coder report, adds the coder's changed files to the scope of the next review, and re-enters the loop, and when no full review follows, the fix-diff pass reads this fix diff before the loop returns. Under an older text that pass went unrun in 3 of the 5 live loops that had a fix coder. The scope clause is by judgment, and no run shows it. The fix dispatch no longer increments the round counter, because a round is a reviewer sent, not a fix dispatched. The effect of the change is unmeasured. Docs-only fixes end the loop with no further review: census of second rounds, where a fix that changed only docs gave the re-review nothing to check. Changed after a seeded round, word for word as tested. The fix findings split into code findings and test gaps. The test gaps go to a Sonnet test-writer in the same message as the fix coder. The coder never edits a test file, and a test-writer failure report becomes a fix finding for the next round. Most of the token rise on the larger seeded tree came from test-writer runs that closed gaps the old loop left open. The split is gone after a bench smoke on one seven-phase ticket: the fix coder takes the test gaps too, and no test-writer runs. The test reviewer still files the gaps. Both loops caught 17 of 19 seeded bugs and passed 19 of 19 hidden checks. The coder-only loop used 34% less agent time, 6% less cost and 27% less Opus cost, with 94% more Sonnet cost and half the test lines. Coder continuity is gone for the same harness reason as Step 3: a coder continued by SendMessage does not keep the loop's run open.

Anchor `agents/spec-leak-check.md`, section `## Output` (evidence: unproven):

The two possible returns: a pass line with the question count, or a flagged list with original, rewrite, and a one-line statement of what the original gives away. Never varied.

## Result

In the work logs, advisory items came at about 2.7 per review run, and 86% of them sat in runs that sent a fix coder anyway. An earlier hand read found that a third to a half of such items name a real defect with one clear correction, and nobody acted on them. On saved trees with saved reviews, a live coder got the fix items alone or the fix items plus the advisory items. With the advisory items it corrected most of the real small defects that those items named, against none without them. Each corrected one was a false statement in a doc, and each new statement agrees with the final code. It skipped the one behavior item with a plain reason, and it reported every advisory item as applied or skipped. Every fix check and every guard check passed in both sets, no tree came out worse, and no change went outside the listed items. The coder cost was level: about 2% more total tokens at the median, slightly less fresh input, about a third more output, and the same tool calls. One tree cost about a third more and one cost about 40% less, so the run-to-run spread is larger than the effect. The gain is quality at no new dispatch: real small defects, mostly doc errors, get corrected in a dispatch that runs anyway. The cost is about 185 always-loaded words in each loop run, and about six seconds per fix coder at the median, inside the run-to-run spread. Limits: the test was a screen. A handful of trees with no harmful change bounds the harm rate only loosely, below about a half, and a handful of scored items on two trees carries the apply result. The test rig built the coder prompt, so the loop's own obedience to the changed lines is untested. No fresh reviewer read the fix diffs, only a hand read. The trees are small TypeScript libraries. The coder skipped the only behavior defect, so the rule mostly corrects docs. Judgment, with no test: no small items on the last repair that no reviewer reads, the ban on a dispatch for advisory items alone, the packet ending, the recap filter, and the choice to leave the reviewer texts alone. A changed line under the reviewer's advisory heading lost verified defects in an earlier seeded round, and a reviewer that learns that its notes get applied can start to file real defects as notes. The live check is the share of advisory rows in the per-finding log that read fixed. It stood at about 3% in the work logs before the change.

## Watch

—

## Back-out

—
