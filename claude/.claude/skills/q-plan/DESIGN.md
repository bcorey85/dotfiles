# QRSPI Orchestrator — Design Notes

**Status**: built 2026-06-12 — `SKILL.md` (62-line dispatcher), four `qrspi-*` agents (`~/.claude/agents/`), inline phase playbooks (`design-phase.md`, `structure-phase.md`). **Verdict (2026-07-07): keep — validated on its home turf (n=2, one per trap class)**. Two retrospective A/Bs vs `/eng-spec` on shipped regret tickets, pre-registered rubrics, full records in `~/dev/plan-ab/.sealed/datachat-tool-history/` and `~/agent-evals/goecharger/`. **Round 1** (datachat, trap = general API knowledge): both lanes passed → ceremony unjustified there; QRSPI's wins were process properties (context economy, risk-tier gating, audit trail) at ~2.3× tokens / ~2.2× wall. **Round 2** (goecharger, trap = codebase-specific hidden coupling, `qrspi-research` pinned to opus for tier parity): **A-pass / B-fail** — goal-blind research documented the unique_id invariant before design intent existed; eng-spec's architect verified the adjacent user-visible invariant and missed the registry one. The External-Contracts template line (added from round 1's calibration) is where the decisive statement landed — the flywheel patch contributed. **Round 3** (cyclopts, trap = interaction with the repo's own `allow_leading_hyphen` feature; tiers equalized; lanes UPGRADED — shared formats + eng-spec spec-review live): **A-pass / B-fail again (2/2 on hidden-coupling traps, n=3 total)**, record in `~/agent-evals/cyclopts/`. Decisive refinement: arm B had a diligent External Contracts section and still missed the contract — **the gap is invariant DISCOVERY, not artifact format**; goal-directed exploration anchors on the feature's mechanics, goal-blind research documents the surface first. Format convergence cannot close this; only research isolation does. **Round 4** (nimblebrain offboarding, trap = headless execution path bypassing the HTTP membership boundary; two variables, one per arm; record `~/agent-evals/nimblebrain/`): **both pass**. Arm A ran STOCK SONNET research and passed (research surfaced "membership validated once, at creation" unprompted) — the routing rule is validated as-deployed, rounds 2–3 were not opus-carried. Arm B ran the new invariant-survey patch and passed for the first time on a hidden coupling — over-delivering (found a second bypass path and a leak seam beyond the shipped fix arc). Caveat: the survey wording was aimed (authored with this trap class in context) — **promising, not proven**; replication on an un-aimed candidate required before any routing change. **Round 5** (niwa ephemeral-session reaping, FINAL; trap = lifecycle-liveness discriminator, a class the survey does NOT enumerate; un-aimed replication, no lane changes; record `~/agent-evals/niwa/`): **A-pass / B-fail — the survey pass did not replicate**. B chose worker-PID-death as its reap predicate (the repo's own false-friend liveness idiom) after explicitly REJECTING the correct jobs-entry-presence signal it had already researched; A's goal-blind research inventoried the dormant session-existence scaffolding as facts and the design anchored reclamation there, fail-closed. An aimed instruction catches its named trap class and does not generalize one class over — instructability-without-isolation is unproven after two attempts (aimed pass, un-aimed fail). Honest caveat: P2 failed BOTH arms (neither named the idle-but-resumable mechanism); A passed on rule, not insight. **Round 6** (cloudredirect playtime sync; trap = reconciliation convergence, design-internal rather than in-repo coupling — accepted deliberately, corpus exhausted; round-5 calibration patches live, A=`q-plan+fm`, B=`eng-spec+survey-v2`; record `~/agent-evals/cloudredirect/`): **both pass, both P2** — the pre-registered weak-evidence branch (textbook-adjacent trap; B named "G-Counter" unprompted; both arms out-designed the shipped fix). Confirms round 1's lesson from the other direction: candidate class dominates lane choice on general-knowledge-shaped traps. Mechanistic patch evidence independent of the outcome: B produced a state→action table for its destructive migration (exactly the new destructive-trigger gate's shape), A's rejected alternatives each name concrete user-visible failure modes and A flipped its round-5 P2 FAIL to PASS; research 3a captured dormant scaffolding (`machines[]` no-producer) unprompted. Attribution stays config-level (n=1, confounded). **Round 7** (gmail-mcp preserved-entries; trap = destructive-predicate class (a), un-aimed for the survey-v2 gate; record `~/agent-evals/gmail-mcp/`): **both P1 FAIL / both P2 PASS — a new verdict class: discovery succeeded, judgment diverged.** Both arms explicitly mapped removeAccount × preserved-only state, surfaced the purge (the shipped fix's behavior) as an alternative, and rejected it as contrary to the feature's intent; the maintainer's credential-hygiene judgment went the other way. Round 5 (pre-patch: blind to the state) vs round 7 (post-patch: state mapped in both arms) is the destructive-trigger gate's before/after — **discovery is instructable; the maintainer's judgment about a mapped state is not**. No lane discrimination (identical decisions); q-plan's P1 streak ends at 5-for-6 on a judgment call, not a discovery miss. Harness change adopted: future rubrics pre-register P1a (interaction discovered & mapped) separately from P1b (resolution matches the shipped fix), because autopilot gates accept the lane's own recommendation and systematically bias P1b. **Standing routing**: `/q-plan` for in-repo hidden-coupling tickets (4-for-4 on discovery in that class) at ~1.5–2× tokens, stock sonnet; `/eng-spec` for general-knowledge risk profiles; `eng-spec+survey-v2` gates validated for destructive-op discovery — the residual gap in BOTH lanes is judgment on discovered states, which is a human-gate problem (engage the gate on destructive-op decisions instead of autopilot), not a lane problem. **Round 8** (ccu-mcp renewal re-entrancy; un-aimed class (a) in a class the survey does NOT enumerate; first round with the structure gate cut; record `~/agent-evals/ccu-mcp/`): **clean sweep — both arms P1a+P1b+P2 PASS**, both independently invented generation-token designs sounder than the shipped handle-identity fix; B additionally flagged a pre-existing second overlap seam beyond the answer key. Key trendline: **eng-spec's un-aimed class-(a) discovery went 0-for-3 pre-patch → 2-for-2 post-patch (rounds 7–8)** — the generative survey rule, not the enumerated class list, is carrying it; round 5's "catches only what it names" reading is superseded for discovery. A's P1a streak: 8-for-8. Structure-gate cut live with no quality anomaly (plan review forced a revision carrying the folded checklist). Cost: B at ~60% tokens / ~70% wall of A, second round running. **Pending routing decision**: one more un-aimed class-(a) pass (devantler-platform queued) → pilot `eng-spec+survey-v2.1` on real hidden-coupling tickets with `/escape lane=` tagging as the prospective safety net; `/q-plan` retains highest-stakes invariant work and unclassified surfaces regardless. Round-7 patch shipped 2026-07-07 (aimed — needs un-aimed validation): shared decision format + eng-spec 15a now require security-terms framing and explicit user sign-off for any decision leaving credentials/user data alive past a removal/revocation intent (tags for the record: `fm-v2` / `survey-v2.1`). Companion protocol question left open for the next round's pre-registration: whether the eval's autopilot rule should carve out sign-off-flagged decisions (engaged gate) — a RUN.md matter, not a skill matter. Open items: qrspi citation patches confirmed working (round-3 research rounds=0, first ever); plan re-review is the remaining latency sink (round-3 rounds=2) — port `/review`'s reviewer-continuity (SendMessage re-review) into review-loop.md; spec-review discovery obligation SHIPPED with the round-4 survey patch (eng-spec 15a) — round-5 un-aimed replication FAILED, keep as insurance with no routing weight; leak-check logging FIXED 2026-07-07: `phase=leak-check` added to the enum and SKILL.md's dispatch now logs it separately — it had been logged under `phase=questions`, so all pre-2026-07-07 "questions" entries CONFLATE the two gates (discount that gate's historical 40% catch rate accordingly); `issues` semantics also redefined log-wide to first-review catch count (final-round count was 0-on-PASS by construction, measuring nothing). Instrumentation-only changes — note in the next round's pre-registration, no behavior delta. Structure review gate CUT 2026-07-07 on metrics (1 forced revision in 6 runs; every other gate 33–67%): its checklist folded into the Plan review, which receives the structure outline as an input — first gate retired by the qrspi-review.jsonl data, the audit trail doing its job. Watch item: research gate is 0-for-6 since the citation-verify patch — cut on ~5 more zero-catch runs.
**Companion**: `SKILL.md` (the how) lives in this directory; this doc is the why
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

Each entry: **decision** / _alternative_ / **why alternative was rejected**.

### 1. Orchestrator-as-router, not orchestrator-as-participant

**Decision**: Orchestrator never reads or paraphrases the ticket. Ticket access is by file path, always to the subagent that needs it.
_Alternative_: Orchestrator reads the ticket once and provides synthesized context to each subagent invocation.
**Rejected**: The orchestrator's prompt sits in the parent context for the entire run. If it names the goal — even as "facilitate QRSPI for adding email notifications" — every step downstream is contaminated and the structural guarantee is fiction. A pure router can credibly be neutral; a participant cannot.

### 2. Subagent orchestrator over five-skill `/clear` chain

**Decision**: One orchestrator skill that dispatches subagents.
_Alternative_: Keep the five sibling skills (already authored), manually chained by the user with `/clear` between each.
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
_Alternative_: Leak-check returns flags only ("question 3 looks goal-leaking").
**Rejected**: Flag-only delegates the hard judgment to the same kind of model that produced the leak. Rewrite-and-diff converts a semantically hard task ("does this leak?") into a mechanically tractable one ("does this survive intent-stripping unchanged?"). One extra LLM call per Q run; trivial cost, structural rather than vibes-based check.

### 4. Human gate at Q→R, no auto-dispatch

**Decision**: Orchestrator pauses after leak-check. Human approves or revises questions before R is dispatched.
_Alternative_: Orchestrator auto-dispatches R as soon as Q (and leak-check) complete.
**Rejected**: Q produces questions with the ticket in context, so leakage is always possible. Auto-dispatching makes the structural guarantee depend on Q being clean, with no human checkpoint. The gate is also where mid-stream course-correction routes back through Q, preserving the "intent has exactly one channel, and it's Q" rule.

### 5. Inline D and S, not subagent D and S

**Decision**: Design and Structure run in the main session as interactive playbook sections.
_Alternative_: Dispatch D and S as subagents like Q, R, and P.
**Rejected**: D and S are interactive — model proposes, human pushes back, iterate. Subagents are functionally one-shot; they don't talk to the user mid-run. Inline keeps the human-in-the-loop where it's needed. The instruction-budget benefit isn't load-bearing for these phases because they don't require clean isolation from prior context.

### 6. Subagent P (budget + format, not isolation)

**Decision**: P (plan) runs as a subagent.
_Alternative_: Inline P like D and S.
**Rejected**: P is non-interactive (final tactical handoff, no human iteration), benefits from a fresh subagent context for instruction budget, and benefits from format-discipline (a dedicated subagent produces the plan template — phase breakdown, automated/manual verification splits, success criteria as testable assertions — more reliably than the orchestrator enforcing it post-hoc). P's claim to subagent-hood is **budget + format, not isolation**. Different justification than Q and R; worth being explicit so the next maintainer doesn't conflate them.

### 7. Recursive goal-agnostic self-description

**Decision**: Every prompt that sits in scope when intent-sensitive content flows through must be neutral — orchestrator, Q's own definition, leak-check's definition.
_Alternative_: Only the orchestrator's prompt is required to be neutral; subagent definitions can name the goal.
**Rejected**: Any prompt in scope when intent-sensitive content flows through is part of the threat model. A `qrspi-questions.md` that reads "you generate questions for the ticket the user wants to implement" primes implementation-shaped thinking before Q has even read the ticket. Cheap discipline, easy to forget, and the kind of thing reintroduced silently during routine cleanup PRs.

### 8. Accept R-output pre-framing, do not leak-check R

**Decision**: No leak-check on R's output. Defense moves downstream to D.
_Alternative_: Dispatch a leak-check on R's output similar to Q's.
**Rejected**: R is summarizing real code. "The system currently supports SMS, push, and webhook channels" is true, relevant, and pre-frames "add email" because email is the obvious next slot. A leak-checker can't distinguish accurate summary from priming without ground truth about intent. Either high false-positive rates (every list of N flagged as priming for N+1) or tune-up-and-catch-nothing. At some point you're auditing for thoughtcrime.

### 9. Enumeration D-prompt over counterfactual D-prompt

**Decision**: D's playbook includes "Name three implementation approaches that are not in scope for this design. If you can't name three, R may have narrowed the design space."
_Alternative_: "What alternatives would R have surfaced if the ticket were different?"
**Rejected**: Counterfactuals require imagination and produce vague output. Enumeration produces concrete artifacts you can read and react to. Useful failure mode: if D can't name three, that's diagnostic information about R's framing, not just a missed prompt. Forcing-function quality.

### 10. Hard ~80-line cap on the orchestrator, not "five-minutes-readable"

**Decision**: Orchestrator prompt has a hard line cap (~80 lines). If it doesn't fit, something has been added that shouldn't be there.
_Alternative_: Qualitative criterion — "a stranger should be able to read it in five minutes."
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
