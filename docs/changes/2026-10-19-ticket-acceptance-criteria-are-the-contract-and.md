---
type: "Change"
change_type: "changed"
title: "Ticket acceptance criteria are the contract, and /verify checks them with or without a plan"
description: "Only the user's explicit sign-off overrides a ticket acceptance criterion. The plan verifier checks every ticket criterion from the ticket's own words, marks one that the plan dropped without sign-off as missing, and marks one about what a user sees as needs-manual unless a captured run shows it. /verify runs ticket-only when no plan exists."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-19T12:08:53-05:00"}
seq: 10
kind: "behavior"
components: ["rule/global-claude-md", "agent/plan-verifier", "skill/verify"]
evidence: ["judgment"]
watches: ["ticket-acs-are-the-contract"]
---

## Change

Global `CLAUDE.md` gains `## Ticket Acceptance Criteria`: the ticket's criteria are the contract. A plan, ADR, criteria file or agent never cuts, narrows or hands one to another repo or team on its own. A sign-off records who, when and their words. A run that shows a criterion failing is reported as failing.

`agents/plan-verifier.md`:

- The oracle is the ticket's criteria, always, plus every phase's criteria.
- A new `### Ticket ACs — never dropped` block. A criterion that the plan cut, narrowed, reworded or handed off is `overridden` only with the user's quoted sign-off, else `missing`. A criterion about what a user sees is `needs-manual` unless a captured run shows the behavior.
- The `What We're NOT Doing` skip covers plan items only, never a ticket criterion.
- A `plan: none` dispatch checks the ticket's criteria and skips the execute job.
- The report table gains the `needs-manual` and `overridden` verdicts.

`skills/verify/SKILL.md`: with no plan, `/verify` fetches the ticket and dispatches the plan verifier with `plan: none`, in place of a stop. A criterion overridden without sign-off routes as a gap.

The edit came in from the work machine in one commit with unrelated terminal scripts.

## Evidence

judgment

### Anchor reasons

Anchor `CLAUDE.md`, section `## Ticket Acceptance Criteria` (evidence: judgment): the user's rule that only their explicit sign-off overrides a ticket criterion, in every repo.

Anchor `agents/plan-verifier.md`, sections `(preamble)`, `## Your scope`, `## Job 1 — Reconcile`, `### Ticket ACs — never dropped`, `### Every item`, `## Output Format` and `## What this is not` (evidence: judgment): the ticket's criteria are always the oracle, a dropped criterion without sign-off is missing, and a user-visible criterion needs a captured run.

## Result

No measurement. The rule came from the user's own decision on the work machine.

## Watch

The share of escapes past plan review that the user catches, from 2026-10-19. A criterion that the plan dropped now fails at `/verify` instead of reaching the user.

## Back-out

Revert the `CLAUDE.md`, `plan-verifier.md` and `verify/SKILL.md` hunks of dotfiles commit `88b5f73d`.
