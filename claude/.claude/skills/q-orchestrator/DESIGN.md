# QRSPI Orchestrator — Design Notes

**Status**: design-only, orchestrator skill not yet built
**Companion**: `SKILL.md` (the how) — once written, lives in this directory; this doc is the why
**Last design pass**: 2026-04-29

## Problem Statement

QRSPI (Questions → Research → Spec/Design → Structure → Plan → Implement) is a structured AI coding workflow for larger features where a monolithic plan would skip steps or leak intent into research. The methodology's load-bearing value is the Q→R isolation — research that documents existing state without being colored by the goal.

The upstream reference implementation chains five sequential `/clear` sessions with manual artifact handoff between steps. This creates per-step copy-paste friction, depends on user discipline to enforce isolation, and surrenders some prompt cache (the parent prefix is rewritten on each `/clear`). This design replaces the session chain with a subagent orchestrator that centralizes the structural guarantees in one place; cache benefits are real but secondary, and not the primary motivation (see Decision 2).

## Architecture

The canonical statement of what exists:

- ~80-line dispatcher orchestrator, never reads ticket, only routes file paths
- Four subagents: `qrspi-questions`, `qrspi-leak-check` (rewrite-and-diff), `qrspi-research`, `qrspi-plan` — each with goal-agnostic self-descriptions
- Two inline phases: D (design) and S (structure), both interactive, both with explicit "name N alternatives not in scope" prompts to fight R-output pre-framing
- One human gate at Q→R, after leak-check passes
- Cache stays warm across the pipeline; ground truth on QRSPI's value comes from retrospective testing on a pre-shipped ticket with pre-registered predictions
- Residual failure mode: R legitimately summarizes existing code, which legitimately pre-frames. Accepted.

## Decision Log

Each entry: **decision** / *alternative* / **why alternative was rejected**.

### 1. Orchestrator-as-router, not orchestrator-as-participant

**Decision**: Orchestrator never reads or paraphrases the ticket. Ticket access is by file path, always to the subagent that needs it.
*Alternative*: Orchestrator reads the ticket once and provides synthesized context to each subagent invocation.
**Rejected**: The orchestrator's prompt sits in the parent context for the entire run. If it names the goal — even as "facilitate QRSPI for adding email notifications" — every step downstream is contaminated and the structural guarantee is fiction. A pure router can credibly be neutral; a participant cannot.

### 2. Subagent orchestrator over five-skill `/clear` chain

**Decision**: One orchestrator skill that dispatches subagents.
*Alternative*: Keep the five sibling skills (already authored), manually chained by the user with `/clear` between each.
**Rejected**: The strong arguments are structural, not cache.

- **Discipline-in-one-place for the recursive goal-agnostic prompt rule.** Five sibling skills mean five places where a routine cleanup PR can silently reintroduce goal-leak. The orchestrator centralizes the contract; the rule is enforced once.
- **Q→R isolation that doesn't depend on user copy-paste hygiene.** The /clear chain's structural guarantee is only as strong as the user remembering not to paste the ticket into the research session. The orchestrator makes the isolation a property of the dispatch logic, not user discipline.
- **Rewrite-and-diff leak-check is cheap enough to be v1 only inside an orchestrator.** Wiring it up as a manual step between two `/clear`d sessions is friction the user will skip; an orchestrator runs it automatically.

**Cache argument was oversold in the original synthesis.** The honest math:
- /clear chain cold run: 5 × ~18-20K main-prefix writes = ~90-100K write premium.
- Orchestrator cold run: 1 parent-prefix write (~18-20K, stays warm the whole run) + 4 subagent-prefix writes (~5-10K each) = ~40-60K.
- Single-run delta: ~2x, not order-of-magnitude. Subagent prefixes are cache misses on their first invocation per TTL window — they don't disappear.
- Order-of-magnitude savings only appear across multiple QRSPI runs in a day, where subagent prefixes amortize.

At once-a-week QRSPI cadence, the cache case is a tiebreaker, not a driver. Future re-litigation of this choice should not lead with cache; if cache is the only argument left, the refactor probably isn't justified yet.

### 3. Rewrite-and-diff leak-check, not flag-only

**Decision**: Leak-check subagent rewrites each question into the most intent-free form it can produce, then diffs against the original. Large diffs flag for human review.
*Alternative*: Leak-check returns flags only ("question 3 looks goal-leaking").
**Rejected**: Flag-only delegates the hard judgment to the same kind of model that produced the leak. Rewrite-and-diff converts a semantically hard task ("does this leak?") into a mechanically tractable one ("does this survive intent-stripping unchanged?"). One extra LLM call per Q run; trivial cost, structural rather than vibes-based check.

### 4. Human gate at Q→R, no auto-dispatch

**Decision**: Orchestrator pauses after leak-check. Human approves or revises questions before R is dispatched.
*Alternative*: Orchestrator auto-dispatches R as soon as Q (and leak-check) complete.
**Rejected**: Q produces questions with the ticket in context, so leakage is always possible. Auto-dispatching makes the structural guarantee depend on Q being clean, with no human checkpoint. The gate is also where mid-stream course-correction routes back through Q, preserving the "intent has exactly one channel, and it's Q" rule.

### 5. Inline D and S, not subagent D and S

**Decision**: Design and Structure run in the main session as interactive playbook sections.
*Alternative*: Dispatch D and S as subagents like Q, R, and P.
**Rejected**: D and S are interactive — model proposes, human pushes back, iterate. Subagents are functionally one-shot; they don't talk to the user mid-run. Inline keeps the human-in-the-loop where it's needed. The instruction-budget benefit isn't load-bearing for these phases because they don't require clean isolation from prior context.

### 6. Subagent P (budget + format, not isolation)

**Decision**: P (plan) runs as a subagent.
*Alternative*: Inline P like D and S.
**Rejected**: P is non-interactive (final tactical handoff, no human iteration), benefits from a fresh subagent context for instruction budget, and benefits from format-discipline (a dedicated subagent produces the plan template — phase breakdown, automated/manual verification splits, success criteria as testable assertions — more reliably than the orchestrator enforcing it post-hoc). P's claim to subagent-hood is **budget + format, not isolation**. Different justification than Q and R; worth being explicit so the next maintainer doesn't conflate them.

### 7. Recursive goal-agnostic self-description

**Decision**: Every prompt that sits in scope when intent-sensitive content flows through must be neutral — orchestrator, Q's own definition, leak-check's definition.
*Alternative*: Only the orchestrator's prompt is required to be neutral; subagent definitions can name the goal.
**Rejected**: Any prompt in scope when intent-sensitive content flows through is part of the threat model. A `qrspi-questions.md` that reads "you generate questions for the ticket the user wants to implement" primes implementation-shaped thinking before Q has even read the ticket. Cheap discipline, easy to forget, and the kind of thing reintroduced silently during routine cleanup PRs.

### 8. Accept R-output pre-framing, do not leak-check R

**Decision**: No leak-check on R's output. Defense moves downstream to D.
*Alternative*: Dispatch a leak-check on R's output similar to Q's.
**Rejected**: R is summarizing real code. "The system currently supports SMS, push, and webhook channels" is true, relevant, and pre-frames "add email" because email is the obvious next slot. A leak-checker can't distinguish accurate summary from priming without ground truth about intent. Either high false-positive rates (every list of N flagged as priming for N+1) or tune-up-and-catch-nothing. At some point you're auditing for thoughtcrime.

### 9. Enumeration D-prompt over counterfactual D-prompt

**Decision**: D's playbook includes "Name three implementation approaches that are not in scope for this design. If you can't name three, R may have narrowed the design space."
*Alternative*: "What alternatives would R have surfaced if the ticket were different?"
**Rejected**: Counterfactuals require imagination and produce vague output. Enumeration produces concrete artifacts you can read and react to. Useful failure mode: if D can't name three, that's diagnostic information about R's framing, not just a missed prompt. Forcing-function quality.

### 10. Hard ~80-line cap on the orchestrator, not "five-minutes-readable"

**Decision**: Orchestrator prompt has a hard line cap (~80 lines). If it doesn't fit, something has been added that shouldn't be there.
*Alternative*: Qualitative criterion — "a stranger should be able to read it in five minutes."
**Rejected**: Line count is a Schelling point you can't argue with. Once "well, it's 120 lines but each section is short" is acceptable, the dumb-dispatcher discipline erodes silently. The five-skill chain stays dumb because it can't be smart; the orchestrator stays dumb only by continued restraint. The hard cap forces that restraint to live in the constraint, not in the reviewer's judgment.

## Residual Failure Modes

These are accepted, not solved. The design knows about them and chose not to fix them.

- **R legitimately pre-frames.** Accurate summary of existing code (channels, extension points, plugin hooks) primes the design space toward the obvious next slot. Unfixable without crippling research utility. Mitigation lives at D, not at R.
- **Leak-check is a tripwire, not a ceiling.** Rewrite-and-diff catches mechanically detectable laundering. Sufficiently sophisticated state-shaped questions ("what extension points exist") may still survive intent-stripping unchanged. Raises the floor; does not establish a structural guarantee.
- **Dumb-dispatcher discipline degrades over time.** The orchestrator stays dumb only by continued restraint. Each "let me just add a check for that" is independently reasonable and collectively fatal. The line cap is the only structural defense; everything else relies on review discipline.
- **Goal-leak in agent self-descriptions can be reintroduced silently.** Recursive goal-agnostic discipline is cheap to enforce and cheap to forget. A "small cleanup" PR six months from now that adds a friendly description to one of the subagent definitions can re-poison the system without anyone noticing.

## Eval Protocol

How to find out whether QRSPI is actually doing work.

- **Ticket selection.** Pick a recently shipped medium ticket with real design choices. Procedural tickets (lint setup, dead code cleanup) don't exercise QRSPI's discipline. The strongest signal comes from tickets with known post-merge regret — follow-up tickets that exist because the original missed something.
- **Pre-registered prediction.** Before checking ground truth, write down: "QRSPI's design step says approach A; I think A was actually better / actually worse / doesn't matter than what we shipped." Pre-registration is what makes the eval falsifiable instead of a story told after the fact.
- **Bias mitigation.** Memory of the original implementation primes the prediction. Two cleaner protocols: pick a ticket from before you joined the team, or have a colleague evaluate the QRSPI output against the PR while you stay blind.
- **Unit of evaluation.** One end-to-end run on a real ticket. After it, decide: orchestrator earns its maintenance cost, OR the questions-hide-the-ticket trick alone (steal the highest-leverage idea, drop the rest) is sufficient.
- **Disqualifying signal.** If QRSPI's design step doesn't surface the post-merge regret on a ticket where the regret exists and is documented, the methodology is doing less than the README claims, and the build cost isn't justified.
