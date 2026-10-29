---
type: "Change"
change_type: "changed"
title: "The `/fix` wrapper's prompt now holds its contract only"
description: "The `/fix` wrapper's prompt is now its contract only: the one-line role, the modifier pass-through, the dispatch step with its four pass-through items and the bare-invocation route, the five status routes with every STOP and do-NOT rule, the escape-log step with its four conditions and command."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["skill/fix", "skill/cc", "skill/branch-recap", "skill/audit"]
evidence: ["removal round"]
watches: []
---

## Change

The `/fix` wrapper's prompt is now its contract only: the one-line role, the modifier pass-through, the dispatch step with its four pass-through items and the bare-invocation route, the five status routes with every STOP and do-NOT rule, the escape-log step with its four conditions and command, the render order, the ask step with its log command, and the Aikido reply step with its three dispositions and post command. Gone: the sentences that explained why each rule exists (the coder-variant mapping, the unpinned-agent aside, `/cc` owning the comments file, the one-round budget, `/branch-recap` reading the queue back, other statuses leaving the gate dirty by design, walkthrough findings as ground truth, a first-pass fix not being an escape, the two double-count notes, the Deviations-entry and `/audit review` cross-references, and the three Aikido asides).

## Evidence

removal round

### Anchor reasons

Anchor `skills/fix/SKILL.md`, section `# Fix Code Review Feedback` (evidence: removal round):

The one-line role: hand the loop the findings, render its packet, raise the modals it cannot. The "maps them to the coder variant and model" clause is gone: every dispatch in both arms carried the mode, the caller, the model, and the findings.

Anchor `skills/fix/SKILL.md`, section `## Modifiers` (evidence: removal round):

The modifier pass-through line. The "agent is unpinned" aside is gone: every dispatch carried `model: sonnet` without it.

Anchor `skills/fix/SKILL.md`, section `## Instructions` (evidence: removal round, judgment):

By judgment, the ask step jumps the editor to each ask, with its question as the note, before it presents the asks. Effect unmeasured. The dispatch step with its four pass-through items and the bare-invocation route, the five status routes with every STOP and do-NOT rule, the escape-log step with its four conditions, the log command, the guard and classify rules, the render order, the ask step with its log command, and the Aikido reply step with its three dispositions and the post command. Gone: the `/cc` ownership aside, the "one-round budget spent" and "`/branch-recap` reads them back" explanations, the "other statuses leave the gate dirty by design" line, the "ground truth" and "not an escape" rationale sentences, the two double-count parentheticals, the "Deviations entry is their record" and "see `/audit review`" asides, and the three Aikido parentheticals. On seven packets (converged, cap-reached, walkthrough escapes, deferred, converged with an ask, plan-impact, Aikido comments) both wordings routed every status the same way, logged the same two escape lines and no handoff escape, and composed both Aikido replies in the required form. The wording without the asides marked the gate on a converged packet that also carried an ask in every run; the wording with them never did.

## Result

Seven canned loop packets on a Go CLI tree (converged with a blocker, a perf item, a false positive and a nit; cap-reached; two user-caught defects on reviewed code; deferred; converged with an ask; plan-impact; two Aikido bot comments), each handed to the wrapper three times per wording on Sonnet with a stand-in loop that returns the packet. Both wordings dispatched once with the same parameters, routed every status the same way, logged exactly two escape lines on the walkthrough packet and none on a handoff, rendered the deferred and plan-impact packets the same, and composed both Aikido replies in the required form. The contract wording marked the gate on the converged-with-ask packet in every run; the full wording never did. Wrapper fresh+output tokens 1.02x; wall and turns unchanged.

## Watch

—

## Back-out

—
