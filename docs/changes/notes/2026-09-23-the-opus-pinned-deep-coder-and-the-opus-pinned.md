---
type: "Change"
change_type: "removed"
title: "The deep modifier now uses the plain coder and code reviewer, with no Opus pin"
description: "On the deep modifier, the code skill, review loop and closing review dispatch the plain coder and plain code reviewer, and the deep modifier changes only the specialist reviewers."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-23T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/code-reviewer", "agent/review-loop", "skill/peer-review"]
evidence: ["judgment"]
watches: []
---

## Change

The deep modifier now uses the plain coder and code reviewer, with no Opus pin. The Opus-pinned deep coder and the Opus-pinned deep code reviewer are deleted. On the deep modifier, the code skill, the review loop, the peer-review skill, the calibrate skill and the branch-wide closing review now dispatch the plain coder and the plain code reviewer with no model argument, and the deep modifier changes only the specialist reviewers.

## Evidence

judgment

## Result

Both agents duplicated a base agent that already pins Opus. The deep coder carried the same prompt as the coder. The deep reviewer added one sentence that pointed depth at cross-file effects, security boundaries, concurrency and second-order contract breaks. That sentence is gone, and no round measured it apart from the model. The gate ranking that favored the deep reviewer compared the Opus tier against the Sonnet tier, and the plain reviewer now runs on Opus. The branch-wide closing review now logs its findings under the plain code reviewer's gate name, so the finding log can no longer separate it from the per-phase reviews. Two agent descriptions leave the always-loaded agent listing. Effect unmeasured.

## Watch

—

## Back-out

restore the two agent files and the dispatch lines.
