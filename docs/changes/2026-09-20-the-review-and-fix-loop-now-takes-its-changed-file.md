---
type: "Change"
title: "The review-and-fix loop now takes its changed-file list, its file sizes"
description: "The review-and-fix loop now takes its changed-file list, its file sizes, and its repo position from one script call at the start of a run."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 8
components: ["agent/review-loop"]
evidence: ["census"]
watches: ["review-loop-scope-script"]
---

## Change

The review-and-fix loop now takes its changed-file list, its file sizes, and its repo position from one script call at the start of a run. The call covers the handoff path and the manual path, and the loop runs no further git command for any of it. That script is new, and it also writes the invocation line that the loop wrote by hand before. A no-model check for it sits beside it in the same directory. The ban on narration became a ban on any response that carries text and no tool call. The two exceptions are the turn straight after a dispatch stub and the final packet. Two bans are new: no poll for a dispatched subagent, and no split of independent tool calls across responses. The loop must not read a file that it is about to hand to a reviewer. The bullet that lists which writes the loop can cause names the helper directory now, not two of the scripts in it. The opencode copy took the same seven changes. (129 more words, about 4,000 in the agent file.)

## Evidence

census

### Anchor reasons

Anchor `agents/review-loop.md`, section `## Step 0: Log the invocation and read the scope (always, first action)` (evidence: removal round, judgment; census):

One Bash call that appends the skill-usage line and prints the review scope, and the fallback to the porcelain state when that call fails. The hand-written fence it replaced stood word for word from the removal round, where both arms logged the line in 12 of 12 runs, and the script writes the same line with the same keys in the same order. The one-call form comes from a census of 15 live loop runs: 72 responses read scope one git command at a time, in every run, and the repo-root lookup alone took a response in 13 of them. Cut by judgment earlier: the paragraph on how the logging hook sees Skill calls and not agents, which the run data showed was unproven on its own. The effect of the change is unmeasured.

Anchor `agents/review-loop.md`, section `## Step 2: Determine review scope` (evidence: removal round; census):

How the loop finds the diff: the handoff files, else the file list that Step 0 printed, plus the second-order supplement, and a ban on a second git call for the sizes, the state, or the repo position. The trimmed arm of the removal round dropped one sentence that forbids a second review of unchanged code, and failed the packet and token checks, so that sentence holds. The Step 0 source and the ban come from a census of 15 live loop runs, which spent 4 responses a run on scope at the median. The ban covers the handoff path too, because the 3 runs that got a handoff block still spent 4, 4 and 8 scope responses. The second-order supplement keeps its first-round-only scope under a counter that starts at zero. The effect of the change is unmeasured.

Anchor `agents/review-loop.md`, section `## What NOT to do` (evidence: removal round, judgment; census):

No write by the agent itself outside the review helper scripts, never the clean mark, no response that carries text and no tool call, no poll for a dispatched subagent, independent tool calls in one response, and no empty converged after a fix coder of the invocation repaired a finding. No shell write, gate mark, or test-intent dispatch in either arm of the removal round. The narration ban became the text-only ban after a census of 15 live loop runs found 55 text-only responses in 14 of them under the old wording. The batch rule rests on 236 of 312 responses with exactly one tool call, and the poll ban on 22 polling responses in 3 runs, the costliest class per response in that census. The write bullet names the helper directory because a third script there now writes the invocation line. Cut by judgment earlier: the rationale under each ban, and the separate no-modal bullet, whose rule now stands once in the role block at the top of the file rather than twice. The last ban now names a repair by a fix coder of the invocation as its condition, by judgment. The older wording named the round number, which a start value from the caller can set above one with no repair: the prompt gave a start value above zero in 294 of 333 work loop runs. The effect of the change is unmeasured.

## Result

Unmeasured. The round that would have measured it gave no usable comparison, so the live runs are the measure from here, at no token cost. Live checks: responses per run, at a median of 12 across a spread of 4 to 54, and scope responses per run, at a median of 4. Two failures to watch for. One is a fall in findings per run, at a median of 2 across a range of 0 to 12. The other is a loss of files between the scope script and the reviewers. In each run dated after 2026-09-20, a file that the script printed and that no reviewer dispatch names is a loss, unless the loop states why it left the file out. No baseline exists, because the script is new. An earlier baseline in this row, 12 of 59, counted prompts that name any file list, not prompts that name the whole list, and it pooled 19 live dispatches with 40 bench ones.

## Watch

—

## Back-out

—
