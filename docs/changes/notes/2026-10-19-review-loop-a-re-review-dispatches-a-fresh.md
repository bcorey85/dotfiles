---
type: "Change"
change_type: "changed"
title: "`review-loop` re-reviews with a fresh reviewer and fixes with a fresh coder each round"
description: "A re-review in `review-loop` dispatches a fresh reviewer of the same type with the Agent tool and passes it the handoff block, and each fix round dispatches a fresh coder. The loop no longer hands back before the re-review result and the full check."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-19T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/review-loop", "shared/handoff-block"]
evidence: ["census", "bench smoke"]
watches: ["review-loop-fresh-re-review"]
---

## Change

`review-loop` now dispatches a fresh reviewer of the same type with the Agent tool for each re-review and passes it the handoff block. Each fix round dispatches a fresh coder. SendMessage leaves the loop's tools. Before, the loop continued the earlier reviewer and coder

## Evidence

census, bench smoke

### Anchor reasons

Anchor `agents/review-loop.md`, section `(preamble)` (evidence: removal round, judgment; census):

Dispatch contract: name, description, the tool list with Agent and no write tool, and no model line, since the callers pass sonnet. Byte-identical in both arms of the removal round, so not itself varied. Gone later: the project memory line, which had no effect while auto memory is off in the settings. SendMessage left the tool list after a census of local loops: the harness ends a subagent run that waits on an agent it continued by SendMessage, and 7 of 8 loops that continued an agent handed back before the re-review result and before the full check.

Anchor `agents/review-loop.md`, section `## Step 3: Dispatch code-reviewer subagent(s)` (evidence: removal round; census):

A fresh reviewer for each re-review, the split threshold read from the sizes Step 0 printed, the split boundary, what each reviewer is passed, including the plan path and its phase with the shared phase-scoped read named, and a ban on a read of a file that the loop is about to put in a reviewer's scope. The trimmed arm dropped three clauses on scope. Every run in both arms dispatched one or two reviewers on the same threshold. The two changed rules come from a census of 15 live loop runs: 9 runs called for a diff stat of their own, and 8 responses in 2 runs read a source file in the repo under review before the reviewer saw it. The plan clause rests on the same census: findings that cite the plan appear in 6 of the 11 live dispatches that got a plan, and in 0 of the 8 that got none. The dispatch now increments the round counter, which is the only place a round is counted. The effect of the change is unmeasured. Reviewer continuity is gone: a re-review is a fresh Agent dispatch that carries the handoff block. Census of local loops: the harness ends a subagent run that waits on an agent it continued by SendMessage, and 7 of 8 loops that continued a reviewer handed back before the re-review result and before the full check.

## Result

The harness now ends a subagent run that waits on an agent it continued by SendMessage. It tells the agent to hand back at once. Since that change, 16 local loops ran. 8 continued an agent by SendMessage, and 7 of those 8 handed back before the re-review result arrived, with a false `cap-reached` and no full check. No loop without SendMessage was cut short. Both arms of a `/code` bench smoke on one plan phase hit the same cut-off. The Sonnet main session stopped there with the fix diff unchecked. The Opus main session resumed the loop and got the full check late. After the edit, 2 of 2 Opus main runs got every re-review result and a passing full check in the first packet, with no forced hand-back. Reviewer cache read showed no rise. No run showed a gain from continuity.

## Watch

review escapes per review run, and loop results in the review metrics.

## Back-out

restore the continuity paragraphs in Steps 3, 3a and 5 and SendMessage in the tool list
