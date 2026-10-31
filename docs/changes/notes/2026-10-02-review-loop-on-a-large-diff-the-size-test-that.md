---
type: "Change"
change_type: "changed"
title: "review-loop: on a large diff, the Opus structure reviewer runs beside the first review"
description: "review-loop: on a large diff (the size test that sends the test reviewer), the Opus structure reviewer runs again beside the first review, on the whole diff, in the same message as the code reviewer and the test reviewer."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 10
kind: "behavior"
reverts: "2026-10-02-review-loop-and-code-reviewer-when-the-structure"
components: ["agent/review-loop", "agent/test-reviewer", "agent/smell-reviewer", "agent/code-reviewer"]
evidence: ["seeded round"]
watches: []
---

## Change

review-loop: on a large diff (the size test that sends the test reviewer), the Opus structure reviewer runs again beside the first review, on the whole diff, in the same message as the code reviewer and the test reviewer. Its findings share the one classification and the one fix pass. Replaces the structure part of the row that removed the Opus structure reviewer

## Evidence

seeded round

### Anchor reasons

Anchor `agents/code-reviewer.md`, section `### Step 3: Structure` (evidence: seeded round, census, removal round):

The structure lens on every pass. The helper placement check flags generic logic left in a feature module. In a seeded round on a web backend, on 12 diffs that buried a generic step, the reviewer caught 11 with the check and 4 without it. It made 1 false flag in 12 runs on each diff set, and its tokens stayed flat. Its naming-is-a-nit line excludes a name that breaks a written rule, which the same naming seeded round backs. It holds the six checks with their prior-art and reference searches, the `[smell]` prefix, and disposition by consequence. It also holds the anti-churn line, the design-decision threshold, and the ban on an audit of pre-existing smells. The checks come from the structure reviewer's scope text, which stood in a removal round. Census of work logs: of 160 structure escapes, 72 had no structure pass before them. The old loop sent a structure reviewer only on large diffs, after convergence. In a seeded round on five large diffs, three runs each, this step caught 39 of 45 planted structure defects. The diffs held 221 to 362 added lines, between the work median and the 75th percentile. The text is word for word as tested. With the Opus structure reviewer beside it, the pair caught 45 of 45. All six misses sit on one diff: a field name against a documented naming convention, and query logic in the wrong layer. An earlier seeded round used one 814-line diff and the first text of this step. This step found 28 of 30 structure issues there, and the Opus structure reviewer found 30 of 30.

Anchor `agents/review-loop.md`, section `## Loop ordering (GATE-CRITICAL — do not reorder)` (evidence: removal round, judgment; census, seeded round, bench smoke):

The iteration order as pseudo-code, which stands word for word from the removal round except for its cap line and its exit line, plus the rule that only the caller marks the session clean and that a dishonest converged status buys an unearned mark. Cut by judgment since: the mechanism paragraph on how the commit gate marks dirty and why no agent event writes clean. No run in either arm ran the clean mark, so that paragraph was unproven on its own. The exit line changed later: the fix-diff pass runs on any exit while a fix diff is unread, with no counter and no cap. A census of 15 live loops found a fix coder in 5, and in all 5 the last dispatch was that coder with nothing behind it. The pseudo-code now counts a correctness round at the reviewer dispatch, in step with the dispatch block, and leaves the sixth line to the specialist counter alone. The exit line bounds the pass by the diffs it has not read instead of by a count, and its condition is an unread fix diff, no longer a coder that ran. The cap line changed last, by judgment on a census of work transcripts, in which 77 of 304 loop packets returned deferred: at the cap it orders no repair and names no status, and it sends the loop to the cap exit of the budget step. The effect of the change is unmeasured. Changed after a seeded round, word for word as tested. The cap line names the correctness round only. The first dispatch sends the eligible specialists in the same message as the code reviewer. A later round sends every reviewer that filed a fix the round before. One message carries the fix coder and a test-writer for the test gaps. The sixth line repeats the loop, with no specialist counter. Changed again when the security and query-cost reviewers left the loop. On a large diff, the first dispatch now sends the structure and test reviewers with the code reviewer, in one message. Census of work logs: the security and query-cost reviewers fixed 0 findings in 53 runs. The structure reviewer keeps its place in the first round after a seeded round on five large diffs. With it, the review caught 45 of 45 planted structure defects, and without it 39 of 45. The fix line changed after a bench smoke on one seven-phase ticket: one fix coder now takes every fix finding, test gaps included, and no test-writer runs. Both loops caught 17 of 19 seeded bugs, and the coder-only loop used 34% less agent time and 6% less cost.

Anchor `agents/review-loop.md`, section `## Step 3a: The structure and test reviewers beside the first review` (evidence: seeded round, census):

A re-review sends a fresh reviewer of the same type for each reviewer that filed a fix the round before, for the same harness reason as Step 3. On a large diff, the Opus structure reviewer and the test reviewer go out in the same message as the first code review. A diff is large when it has a non-test file and either 40 or more added lines or a new source file. That is the size test of the old structure trigger. The structure reviewer takes the whole diff, the test reviewer takes the test files, and the code reviewer keeps the other files. All findings share one classification and one fix pass. A reviewer that files only questions or small items stops after its first pass. The first review with other reviewers beside it comes from a seeded round on two trees. There, the median loop time, priced at work agent speeds, fell from 1362 s to 1082 s and to 778 s. Unfixed findings at exit fell from 2 to 0 per loop. The test reviewer on the test files comes from a seeded round on one 814-line diff, five runs each. With it, the review found 15 of 15 test gaps against 10 of 15, at 36% less Opus cache read at the median. The security and query-cost reviewers no longer run. Census of work logs: they ran 53 times over 142 dispatches and fixed 0 findings, and none of 306 logged escapes was a security defect. The structure reviewer runs again after a seeded round on five large diffs of 221 to 362 added lines, three runs each. With it, the review caught 45 of 45 planted structure defects, against 39 of 45 for the code reviewer and the test reviewer. Both caught 45 of 45 planted bugs, with no false findings. Over the 15 runs of each pair, the structure pair used 27% more Opus cache write, 8% more cache read and 18% less output than the test pair. Its median wall time was 45 s against 56 s. The live shape runs all three reviewers, and no round ran it as one.

Anchor `agents/spec-leak-check.md`, section `## Process` (evidence: unproven):

The rewrite-and-diff method: read only the questions file, never the ticket beside it, rewrite each question into its most intent-free form, and treat the size of the rewrite as the evidence of leakage. The exploration map gets the same pass. This is the whole mechanism of the agent and no round has tested whether a rewrite diff detects a planted leak.

## Result

On five seeded large diffs (221 to 362 added lines), three runs each: planted structure defects caught 45 of 45 with the structure reviewer beside the code reviewer, against 39 of 45 by the code reviewer with the test reviewer. Planted bugs 45 of 45 both, false findings 0 both. All six misses sit on one diff: a field name against a README convention and query logic in the wrong layer, missed in 3 of 3 runs. The pair with the structure reviewer, per run against the pair with the test reviewer: Opus cache write +27%, cache read +8%, output -18%, wall median 45 s against 56 s. The live shape runs all three reviewers and costs more than either pair; it was not run as one. Check after the edit: structure findings fixed per loop and structure escapes in the work logs

## Watch

—

## Back-out

—
