---
type: "Change"
title: "The diff reviewer's rule about trusting a reported check no longer repeats a generic rule"
description: "The diff reviewer's rule about trusting a reported check no longer repeats a generic rule."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 17
components: ["agent/code-reviewer", "rule/global-claude-md"]
evidence: ["census", "judgment"]
watches: []
---

## Change

The diff reviewer's rule about trusting a reported check no longer repeats a generic rule. The same file names that generic rule two lines above, and the global rules file states it with no condition. The conditional half stands, because it is the only part the reviewer file adds. The opencode copy took the same change.

## Evidence

census, judgment

### Anchor reasons

Anchor `agents/code-reviewer.md`, section `## Reviewer-Specific Tool Use` (evidence: removal round, census, judgment):

What remains: trust a reported check, and stay in scope with two standing exceptions. The block survived a removal round: the contract-only text that matched the full prompt in two replicates at opus held both bullets. The first bullet dropped the sentence that repeated a generic rule, which this file names two lines above and the global file states with no condition. A census of this machine's saved reviewer dispatches, with package-runner prefixes allowed, found a re-run of the project's type check in 13 of 40 bench dispatches and a check run in 1 of 19 live ones. It is a guide only, and no count from the work machine is on file. The handoff reported a passing check in 1 of those 59 prompts, and that dispatch ran no checker, so saved data cannot show what this bullet does. Two earlier counts were wrong. About a third of all saved dispatches came from a matcher that accepted a checker name anywhere in a command, including inside a search. Two of fifty-nine came from a matcher that rejected a checker behind a package-runner prefix. By judgment, the reviewer no longer runs the full suite or a long gate, only a check scoped to the diff's files, because the review loop runs the full suite once at its end. Effect unmeasured. By judgment, the bullet on scope now names a third standing exception: the prior-art search of the structure step. That search must look outside the diff to name an existing helper.

## Result

Effect unmeasured. The condition reached almost no saved dispatch, so this removes a repeat rather than changes behavior. Live check, against runs dated after 2026-09-20: the share of reviewer dispatches that run a project checker. No baseline from the work machine is on file, and only that one counts. As a guide from this machine, with package-runner prefixes allowed, 13 of 40 bench dispatches re-ran the project's type check. One of the nineteen live dispatches ran a check, in a toolkit session where the scripts were the code under review. That share must not rise. Two earlier figures in this row were wrong. The first, about a third of all saved dispatches, came from a matcher that accepted a checker name anywhere in a command. The second, two of fifty-nine and none live, came from a matcher that rejected a checker behind a package-runner prefix.

## Watch

—

## Back-out

—
