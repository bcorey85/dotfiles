---
type: "Change"
title: "review-loop and code-reviewer: the security and query-cost reviewers no longer run in the loop"
description: "review-loop and code-reviewer: the security and query-cost reviewers no longer run in the loop."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 8
components: ["agent/review-loop", "agent/code-reviewer"]
evidence: ["census"]
watches: []
---

## Change

review-loop and code-reviewer: the security and query-cost reviewers no longer run in the loop. The code reviewer owns security and query cost on every pass, beside correctness and structure

## Evidence

census

### Anchor reasons

Anchor `agents/code-reviewer.md`, section `(preamble)` (evidence: seeded round, removal round, judgment, census):

Dispatch contract: name, description, tools, and the one-line role. Gone: the project memory line, which had no effect while auto memory is off in the settings. With auto memory on, that line gives a read-only reviewer the write tools and a memory prompt. The opus pin stays because sonnet at this gate missed planted defects that the same prompt caught on opus. The role line's restraint clause went with the judgment text: two replicates at opus found the reviewer without it equal on recall and on false findings. The description is a routing line: what the agent is, who dispatches it, and any rule that the dispatcher needs. A census of this machine's top-level dispatches, a guide only, found none that menu text alone picked, and no dropped dispatcher rule had the description as its only home. The description and the role line changed when the security and query-cost reviewers left the loop. The reviewer now owns correctness, security, query cost and structure on every pass. It leaves the cull of low-value tests to the test audit at branch exit. Census of work logs, without this machine's toolkit and eval sessions: the two removed reviewers ran 53 times over 142 dispatches and fixed 0 findings. None of the 306 logged escapes was a security defect.

Anchor `agents/code-reviewer.md`, section `## Review Process` (evidence: census):

The heading over the three review steps, with no text of its own. It replaced the four bullets that gave other lenses to specialist reviewers, when this reviewer took security, query cost and structure. Census of work logs: the security and query-cost reviewers fixed 0 findings in 53 runs. Of 160 structure escapes, 72 had no structure pass before them.

Anchor `agents/review-loop.md`, section `## Inputs (from the dispatch prompt)` (evidence: removal round; census, seeded round):

The dispatch arguments: mode, caller, lane, the plan path with its phase, the handoff block, the deep and specialist flags, the reviewers list, and no-review. The trimmed arm dropped only the sentence on why lane must be set. That arm failed the packet and token checks, so the whole text holds. The plan argument is newer, from a census of 19 live reviewer dispatches: 8 carried no plan at all, and in 6 of those 8 the loop's own prompt already held a plan path. The effect of the change is unmeasured. The deep flag names the specialist variants only. The fix coder and the code reviewer run as is, because the Opus coder showed no gain over Sonnet 5.5 after review. The specialist flags and the reviewers list are gone, because the loop no longer runs the security and query-cost reviewers. Census of work logs: the security and query-cost reviewers fixed 0 findings in 53 runs. The size of the diff alone sends the structure and test reviewers, so no argument picks them. The deep flag now changes nothing in the loop, because every reviewer that the loop sends already runs on Opus.

## Result

At work, the two passes ran 53 times over 142 dispatches and fixed 0 findings, and 0 of 306 logged escapes were security. The loop drops those dispatches. Check after the edit: security and query-cost escapes in the work logs

## Watch

—

## Back-out

—
