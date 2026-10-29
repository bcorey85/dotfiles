---
type: "Change"
change_type: "changed"
title: "The review skill's prompt is now its contract only: the one-line role, the modifier pass-through"
description: "The review skill's prompt is now its contract only: the one-line role, the modifier pass-through, the dispatch step with its five pass-through items, the five status routes with every STOP and do-NOT rule, the seven render lines in order, the ask step with the log command."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-16T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["skill/branch-recap"]
evidence: ["removal round"]
watches: []
---

## Change

The review skill's prompt is now its contract only: the one-line role, the modifier pass-through, the dispatch step with its five pass-through items, the five status routes with every STOP and do-NOT rule, the seven render lines in order, the ask step with the log command, the nothing-outstanding line, and the four plan-impact steps. Gone: the asides about the agent's instructions and its pin, the empty-fixed-list and stopping-rule rationale, the auto-fix-is-most-wrong sentence, the ask-outcome yield sentence, the normal-completion and branch-recap notes, the gate-dirty-by-design line, the modal-blocks note, and the verify/adr cross-references.

## Evidence

removal round

### Anchor reasons

Anchor `skills/review/SKILL.md`, section `# Code Review` (evidence: removal round):

The one-line role: dispatch the loop, render its packet, raise the modals it cannot. The "its instructions never enter this context" aside is gone: the wrapper dispatched the same agent with the same parameters in every run without it.

Anchor `skills/review/SKILL.md`, section `## Instructions` (evidence: removal round, census, judgment):

By judgment, the ask step jumps the editor to each ask, with its question as the note, before it presents the asks. Effect unmeasured. On a census of work turn ends, where 1957 of 3140 turn ends with a human reply asked no question: end the turn only at a STOP or a wait, and take any other reversible step without asking leave. Effect unmeasured. The dispatch step with its five pass-through items, the five status routes with every STOP and do-NOT rule, the seven render lines in order, the ask step with the log command, and the nothing-outstanding line. The rationale clauses (empty fixed list is a bug, stopping-rule receipt, auto-fixing an ask is most wrong, the ask-outcome yield sentence, the normal-completion and branch-recap notes, gate dirty by design) are gone: the wrapper routed every canned status, rendered every line, marked the gate only on converged or deferred, and never auto-fixed an ask in every run without them, at the same tokens. The cap-reached route keeps the sentence that the dirty session keeps the commit blocked, because the code skill's round found the wrapper marks a capped phase done without it. The missing-receipt sentence under class_closure is kept but does not work in either wording: with no class_closure line in a converged packet the wrapper wrote `none` and marked the gate clean in most runs of both arms. The log command takes the round count that the loop returns, the form that the fix skill has. That label was not itself varied.

## Result

Against a stand-in loop that returns a canned packet, six packet shapes (converged with every field, cap-reached, converged with no closure receipt, deferred, converged with an ask, plan-impact), three runs per shape per arm. The contract text dispatched the same agent with the same model and parameters, once, with no stray agent, no fix skill, and no edit in every run, rendered every line the full text rendered, marked the gate only on converged and deferred, never auto-fixed an ask, and surfaced the plan-impact packet before any other dispatch. Wrapper fresh+output tokens 0.98x; wall and turns unchanged. One rule failed in both wordings: with no closure receipt in a converged packet, the full text wrote a receipt of `none` and marked the gate clean in every run, the contract text in two of three.

## Watch

—

## Back-out

—
