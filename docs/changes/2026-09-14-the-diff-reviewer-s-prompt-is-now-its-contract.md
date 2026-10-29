---
type: "Change"
change_type: "changed"
title: "The diff reviewer's prompt now holds its contract only"
description: "The diff reviewer's prompt is now its contract only: the one-line role, the project-memory paragraph, the four specialist-ownership bullets, how it finds its scope, read every file in scope and the project conventions file, the report template, and two tool-use rules."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-14T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/code-reviewer", "agent/review-loop", "agent/smell-reviewer"]
evidence: ["removal round"]
watches: []
---

## Change

The diff reviewer's prompt is now its contract only: the one-line role, the project-memory paragraph, the four specialist-ownership bullets, how it finds its scope, read every file in scope and the project conventions file, the report template, and two tool-use rules. Gone: the pointers to the shared calibration and vocabulary files, the flag and do-not-flag lists, the three required audits with their two guard sentences, the categorize step, and the closing self-check. One sentence in the report template keeps the plan-impact prefix that the review loop scans for. The shared files are unchanged and the four specialist reviewers still load them. Five files that referred to the removed text now refer to what remains: the deep variant's inheritance line, the calibration file's adopter list, the smell reviewer's deferral line, the review loop's dispatch note, and the audit skill's diagnosis table.

## Evidence

removal round

### Anchor reasons

Anchor `agents/code-reviewer.md`, section `### Step 1: Determine Scope` (evidence: removal round):

How the reviewer finds the diff: the handoff block first, else the git working state. Kept verbatim in the contract-only text that matched the full prompt in two replicates at opus. Not itself varied.

Anchor `agents/smell-reviewer.md`, section `## Explicitly NOT your scope` (evidence: removal round):

The four deferrals and the single closing `Note:` rule. Byte-identical in both arms; every out-of-domain observation landed as a closing note in both.

## Result

Two replicates at opus over nine frozen trees, three of them carrying a keyed regression, graded blind with every fix-level claim executed against the tree: the contract-only reviewer caught the same keyed regressions as the full prompt in both replicates, and the two prompts both filed zero false findings in both replicates. It did so at about seven tenths of the tokens per review, nearly all of the saving in cache reads, with output tokens equal, tool calls about one eighth fewer, and wall-clock about one tenth longer. It filed more nits, and it used the blocker tag on most of its fix items where the full prompt used it on none, so the blocker share in production is the number to watch. The loaded prompt drops from about 4,100 words across three files to about 700 in one file. The plan-impact sentence and the memory paragraph are unmeasured.

## Watch

—

## Back-out

—
