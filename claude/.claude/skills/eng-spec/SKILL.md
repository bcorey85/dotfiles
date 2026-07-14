---
name: eng-spec
description: Spec a feature — goal-blind research first, then architect exploration, then design decisions resolved with you one at a time and logged to a decision ledger as they land, then a finalized plan. Auto-detects scope (fe/be/fullstack). Optionally writes the spec to disk and/or dispatches coders.
allowed-tools:
  [
    Bash,
    Read,
    Write,
    Edit,
    Glob,
    Grep,
    Agent,
    AskUserQuestion,
    SendMessage,
    Skill,
  ]
---

# Engineering Spec

The one planning lane. Consumes whatever context is already in the thread (a
`/pull-ticket` result, a pasted description, a spec file). Does NOT fetch
external context itself.

**The task directory is the memory; the conversation is not.** Every phase lands
its output on disk before the next one starts — `00-ticket.md`, `01-questions.md`,
`02-research.md`, `03-decisions.md`, then `spec.md`. Design resolution is long and
discursive by design, and a long conversation gets compacted. Anything that lives
only in the thread when that happens is gone. Write first, then continue.

**The order of the first two phases is the point of this skill.** Research runs
before anyone — you, the architect, or me — has read the ticket for design.
Facts land on the table before a goal can shape which facts get looked for. This
is the only step in this system with a clean result behind it. Do not reorder it,
do not "just have the architect do the research too," and never let a goal word
reach the research agent.

## Modifiers

- `be` / `backend` — force backend-only scope
- `fe` / `frontend` — force frontend-only scope
- `fs` / `fullstack` — force fullstack scope

## Phase 1: Ticket

1. **Use the context already in the thread.** If the skill argument is a path to
   a ticket/spec file, read it. If a `/pull-ticket` result is in the thread, use
   it. Do NOT fetch from Jira/Notion yourself — if a ticket is relevant and
   wasn't pulled, tell the user to run `/pull-ticket` first.

2. **If no context is apparent**, ask: "What are we building? Describe the
   feature or paste a ticket."

3. **Check for an existing spec** — Glob `docs/eng-specs/**/spec.md`. If one
   matches, read it and ask: "Found an existing spec — update it or start fresh?"

4. **Open the task directory.** `docs/eng-specs/<slug>/` (Jira key if there is
   one, else kebab-case from the description). `Write` the ticket verbatim to
   `00-ticket.md` — **raw fields only, no paraphrase, no summary, no goal words
   of your own.** You are a courier here. A paraphrased ticket is a ticket with
   your reading already baked into it.

## Phase 2: Goal-blind research (before any design thinking)

5. Dispatch, in order — each is pinned, so omit `model`:

   - **`spec-questions`** with the path to `00-ticket.md`. It writes
     `01-questions.md`: objective codebase questions that never reference the
     ticket's goals.
   - **`spec-leak-check`** with the path to `01-questions.md`. It rewrites each
     question into its most intent-free form and diffs. Any question whose
     rewrite differs materially has leaked the goal — **fix those questions and
     re-run the check** before proceeding.
   - **`spec-research`** with the path to `01-questions.md` — **and nothing
     else.** It must never see the ticket, the slug, or any goal word. It
     inventories what is *there*, factually, with `file:line` refs, and writes
     `02-research.md`.

6. **Hand `02-research.md` to the user and stop.** Let them read it before either
   of you has proposed anything. This pause is not a formality — it is the only
   moment in the process where the facts are not yet serving an argument.

## Phase 3: Scope

7. **Determine scope** (frontend / backend / fullstack) from the ticket, the
   research, and the codebase. If a scope hint was passed (`be`/`fe`/`fs`), use
   it. If genuinely ambiguous, ask. Then state it: "This is [scope]. I'll spin up
   [architects]. Sound right?"

8. **Go lean?** Default is NO — run the architects. Skip Phases 4–7 only if ALL
   of these hold:

   - Pure configuration with zero implementation choices (install a package, add
     an env var, flip a flag)
   - No new files, no changed service/module signatures
   - No data-model, API-contract, or state-management decisions
   - The whole change is under 5 lines of diff

   **A well-written ticket is NOT a reason to skip the architect.** Tickets
   describe the PM's intended approach; architects validate that approach against
   the actual codebase. An "Approach" section is context FOR the architect, not a
   replacement for one.

   If skipping: confirm explicitly with the user ("This is pure configuration —
   skip the architect and go lean?"), write the plan from existing patterns, and
   **still dispatch a coder in Phase 8 if they choose to implement** — the coder
   dispatch is what triggers the review chain. In the saved spec,
   `## Decisions` reads `None — pure configuration; the constraints that forced it
   are under Constraints.` and `## Approaches Considered and Not Taken` reads
   `N/A — go-lean path (no architect ran)`. A dangling empty section is
   indistinguishable from one the process forgot to fill.

   **If you find yourself wanting to write a real decision block, the go-lean
   call was wrong.** Back out and dispatch the architect. A decision worth
   recording means at least one of the four conditions above was false.

   When uncertain, run the architect.

## Phase 4: Architect exploration (explore only — no design yet)

9. **Launch architect agent(s)** by scope (both in parallel for fullstack —
   exploration has no contract dependency). Omit `model`; their frontmatter pins
   it. Give each the ticket and **`02-research.md`**. Read
   `~/.claude/skills/_shared/invariant-survey.md` and insert its "Dispatch text"
   section verbatim as item 2:

   > Explore only — do NOT produce an implementation plan yet. The research
   > document you were given was produced without sight of the ticket; treat it
   > as the factual ground truth and say so plainly where the ticket's premise
   > and the research disagree. Return an **exploration brief**:
   >
   > 1. **Current state** — what exists today, with `file:line` refs
   > 2. <insert the "Dispatch text" section of `_shared/invariant-survey.md` here,
   >    verbatim — it begins "**Invariant survey (do this BEFORE thinking about the
   >    feature)** — inventory the standing invariants…">
   > 3. **Patterns** — to follow and to avoid, with refs
   > 4. **Constraints** — technical and convention constraints you found
   > 5. **Counter-priming** — name three implementation approaches you considered
   >    and are NOT recommending, one line each on why not. If you cannot name
   >    three, say so explicitly — that is diagnostic information about how
   >    narrowly you framed the problem, not a step to skip.
   > 6. **Decision points** — every place two or more viable approaches exist,
   >    each with options, pros/cons, and your recommendation.
   > 7. **Open questions** — ambiguities only the user can resolve.
   >
   > Exception: if the task genuinely has NO design decisions (exactly one
   > reasonable approach), say so and return the full plan instead — but item 5
   > (counter-priming) is still REQUIRED, prepended to the plan. "There was
   > nothing to decide" is itself a claim, and it is the one most worth checking.

10. If every architect returns a full plan (zero decision points, zero open
    questions), skip Phases 5–6 and the step-15 finalization; go to Phase 8.

## Phase 5: Open the decision ledger (mechanical — no thinking, no asking)

**Do this before the first design question leaves your mouth.** Phase 6 is a long
conversation and long conversations get compacted; a decision that exists only in
the thread is a decision you will silently lose, along with the reasoning that
produced it. The ledger is the fix, and it only works if it exists *before* the
talking starts.

11. **`Write` `03-decisions.md`** into the task directory, from the architect
    briefs alone — every decision point and open question they returned, one
    checklist line each, in the order you intend to raise them:

    ```markdown
    # Design Decisions — <slug>

    > Research: ./02-research.md
    > Status: 0/N resolved

    ## Queue

    - [ ] D1. <decision point, one line> — from <architect>
    - [ ] D2. <decision point> — from <architect>
    - [ ] Q1. <open question> — from <architect>

    ## Resolved

    ## Direction & Constraints

    <!-- Anything the conversation established that is NOT a decision: a
    constraint the user named, a direction ruled out, a premise of the ticket
    they corrected. These are the first casualties of compaction and nothing
    else captures them. -->
    ```

    Items are ADD-ONLY: a decision that surfaces mid-conversation gets appended to
    the queue, never handled off-ledger.

## Phase 6: Interactive design resolution — in prose, one at a time, logged as it lands

**This is the point of the skill.** Everything else is scaffolding around it.

12. **Present understanding FIRST**, before any decisions: current state, the
    patterns found (ask the user to confirm they are the RIGHT ones to follow),
    constraints, and the architect's **three counter-primed approaches**. The
    user needs a chance to catch a wrong pattern — and to see what was ruled out
    on their behalf — before either propagates into every downstream decision.
    Whatever this exchange settles — a rejected direction, a corrected premise, a
    constraint the user names — goes under `## Direction & Constraints` in the
    ledger *as it lands*, not later.

13. **Write the answer down before you ask the next question.** The moment a
    decision resolves, `Edit` `03-decisions.md`: append the full four-field block
    (`~/.claude/skills/_shared/design-decision-format.md`) under `## Resolved`,
    tick its queue line, bump the `Status:` count. Not a note-to-self, not a
    one-liner — the finished block, because Phase 7 architects and the saved spec
    both read this file and nothing reconstructs the reasoning later.

    **The ledger is the record; your context is a cache.** If the conversation was
    compacted — or you are at all unsure what has been settled — re-read
    `02-research.md` and `03-decisions.md` before continuing. **Never reconstruct a
    resolved decision from memory, and never re-ask one that is already ticked.**

14. **Resolve decision points ONE AT A TIME, in prose. Never `AskUserQuestion`
    here.** A multiple-choice modal with a recommended option pre-selected is a
    rubber stamp: it invites a click, not a conversation, and the clarifying
    questions the user asks back — the constraints and intent that live only in
    their head — never get asked. The decision points ARE the interview. Walk the
    ledger's queue and put each one to the user as written English:

    - what the decision is, and why it is live (what in the research forces it)
    - the options with their real costs — **all of them**, and what each one makes
      worse
    - your recommendation, stated last and stated as a recommendation
    - **then stop and wait.** Do not bundle the next question into the same turn.

    Expect the user to answer with a question rather than a choice. That is the
    system working, not a stall: follow it wherever it goes, and log whatever it
    surfaces under `## Direction & Constraints`. Ask follow-ups freely; there is no
    question quota.

    **Never resolve a decision by recommending harder. Ask, and wait for words.**

    **Split the check out of the decision.** When a decision contains a claim
    shaped like *"we know X because we looked at Y"* — does this record exist? is
    this the same user? is this process still alive? is this value unique? — that
    check is its own decision. Do not let it ride along as a subordinate clause;
    every failure this system has ever shipped lost it exactly there. Ask it as
    its own question. (If you want it attacked, that is what `/falsify` is for —
    you invoke it, on a claim you name. It is not a gate and it does not run
    itself.)

    **Scope gate (blocking).** The moment a decision would add a migration,
    index, table, endpoint, or dependency the ticket did not imply: **stop and
    say so plainly, with the cost.** Do not proceed on your own recommendation.
    Scope is the ticket-owner's call, and it is the one thing you cannot work out
    for yourself.

    Do NOT write the spec and do NOT dispatch finalization until every decision
    point and open question is resolved. **The completeness test is mechanical:
    every queue line in `03-decisions.md` ticked.** Not "the conversation feels
    finished" — read the ledger and check.

## Phase 7: Architect finalization

15. **Continue each architect via `SendMessage`** — its exploration context is
    intact, so send the path to `03-decisions.md` plus the instruction to produce
    the full plan per its Output Format. Do NOT re-litigate resolved decisions;
    they carry the user's authority. If the agent is no longer addressable, fall
    back to a fresh dispatch with its brief verbatim, `02-research.md`, and
    `03-decisions.md` — the ledger is written to make that fallback lossless.

    Send the ledger **by path, and by path only**. Re-typing the decisions into
    the dispatch prompt from your context is exactly the compaction-lossy move the
    ledger exists to prevent, and the two copies will not agree.

    **Fullstack ordering**: finalize `backend-architect` first — its plan must
    include a clearly defined **API contract** (endpoints, methods,
    request/response shapes, status codes). Then finalize `frontend-architect`
    *with* that contract, so it designs against it rather than inventing one.

16. **Synthesize the finalized plan(s).**

    - **`DESIGN GAPS` returned by an architect**: resolve each with the user in
      prose (step 14's rule holds — no modal),
      append it to `03-decisions.md` as a decision block (it is a Phase-6
      decision that arrived late, not a footnote), **then send the resolution back
      to that architect** and take its revised plan. Its guess may have shaped
      steps and success criteria well past the flagged line; hand-patching the one
      marked spot leaves the rest built on the guess.
    - **Carry the counter-priming into `## Approaches Considered and Not Taken`**
      — the three ruled-out approaches, each with its failure mode.
    - **Write `## Constraints` and `## External Contracts` — nothing upstream
      produces them.** `## External Contracts` is mandatory: name each
      provider/API/platform contract the change touches, the invariant it
      imposes, and what breaks if violated — or state "None" explicitly. Where
      the change alters what an external tool ACCEPTS or ENFORCES at runtime
      (verifier, policy engine, admission controller, parser, migration runner),
      each acceptance claim states its evidence class — `exercised` or
      `declared-only`. Schema text and in-repo precedent describe intent, not
      runtime behavior.
    - **Fullstack: weave, don't concatenate.** Merging as "backend phases, then
      frontend phases" is the horizontal anti-pattern `plan-format.md` forbids —
      a layer phase produces no end-to-end pass/fail signal for `/code`'s gates.
      Interleave into vertical slices: each phase delivers one increment of
      user-observable behavior end-to-end, independently verifiable. The API
      contract fixed in step 15 is what makes this safe. A phase stays
      single-layer only when the work genuinely is (migration-only, infra-only).

## Phase 8: User choice

17. **HARD STOP — no spec write, no coder dispatch, until the user answers.**

    Ask both questions in ONE **AskUserQuestion** call ("Save to disk?" and
    "Implement now?"). The blocking modal is the mechanism that makes this stop
    unskippable; asked as prose, it has been skipped before. Presenting the plan
    in conversation is fine. Writing the spec or dispatching coders before the
    answers is NOT.

    **This is the ONLY legal `AskUserQuestion` in the skill** — two mechanical
    yes/nos with nothing to discuss. Design decisions (Phase 6) are prose, always;
    a modal there buys a click instead of the user's knowledge.

    **Save to disk?**
    - Yes → Write the spec to `docs/eng-specs/<slug>/spec.md` using the template
      below. Its `## Decisions` is **copied from `03-decisions.md`**, block for
      block — do not re-derive it from the conversation, and do not summarize.
      `## Direction & Constraints` from the ledger feeds `## Constraints`. The
      research and decision artifacts stay beside the spec — they are the evidence
      the decisions were made against.
    - No → the spec stays in the conversation, and the task directory is removed.

    **Implement now?**
    - Yes, **more than one phase** → the spec must be saved (save it even if they
      said no above — explain why), then invoke `/code` with the spec path.
      `/code`'s phase-boundary machinery keys off the plan's risk tags; a raw
      coder dispatch bypasses every gate the plan just defined.
    - Yes, single-phase → dispatch coder(s) by scope: `backend-coder`,
      `frontend-coder`, or BOTH in parallel for fullstack (frontend also gets the
      API contract). **Always dispatch a coder. Never implement inline** — the
      dispatch is what triggers the review chain.
    - Later → stop here.

18. **Present summary**: key decisions, file written (if saved), what was
    implemented (if coded). Remind the user to check Figma if frontend work is
    involved.

    **If any code changed this session**, say: "Auto-dispatching `/review` to
    check the implementation before committing," then invoke `/review`. The
    review is triggered by code changing, not by how it changed — never skip it
    because no coder was dispatched.

## Template (for saving to disk)

The spec has two layers in ONE file: a judgment layer (what a human reads at the
gate) and an implementation layer (what `/code` executes, in the shared plan
format so its phase gates work).

**`## Phase Status` is hoisted to the top, above both layers.** It is the one
section that changes after the spec is written — `/code` ticks it as phases land —
and the whole point is that opening the file answers "where are the agents?" on
the first screen, without scrolling past the judgment layer. Everything else in
`plan-format.md` still applies in full; only the checklist moves.

```markdown
# Title

> Jira: JIRAPROJECT-TICKETNUMBER (if applicable)
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: YYYY-MM-DD

## Summary

One paragraph on what this accomplishes.

## Phase Status

<!-- Hoisted here from the Implementation Plan below so a peek at the file shows
progress immediately. Updated by /code after each phase completes + review passes.
Source of truth for "which phase is next" across /clear boundaries. Do not delete,
do not move back down. Lines and risk tags follow plan-format.md exactly. -->

- [ ] Phase 0: Contracts — frozen at plan approval (risk: high)
- [ ] Phase 1: Walking skeleton (risk: low|high)
- [ ] Phase 2: [name] (risk: low|high)
- [ ] Phase N..N+3: Refactor → Verify → Orient → Recap (closing-phases.md)

## Decisions

<!-- Copied verbatim from 03-decisions.md's ## Resolved section — that ledger was
written as each decision landed, and it, not the conversation, is the record.
Every decision uses the four-field block from
~/.claude/skills/_shared/design-decision-format.md: Choice / Reasoning /
Alternatives rejected / Trade-off accepted. Never a table with one-line
rationales. -->

## Approaches Considered and Not Taken

<!-- The architect's three counter-primed approaches. One line each: the
approach, and the concrete failure mode that ruled it out. This is a different
axis from a decision's "Alternatives rejected" — these are whole approaches to
the feature, not options within one decision. It is what stops the next reader
from re-proposing what was already ruled out. If the architect could not name
three, say so, and say how many it named. -->

## Constraints

<!-- What was fixed before design began and could not be traded away: platform
limits, existing contracts, non-negotiables. A "decision" with no real
alternative belongs HERE — if you cannot name an option a constraint killed, it
was never a decision. -->

## External Contracts

<!-- Mandatory: every provider/API/platform contract touched + the invariant it
imposes + what breaks if violated, each acceptance claim tagged `exercised` or
`declared-only`. Internal invariants with blast radius (identity construction,
hidden couplings) belong here too. "None" must be stated explicitly. -->

## Approach

- Breakdown by area — area framing lives in THIS section only; the Implementation
  Plan below slices vertically, never by area
- Specific patterns to follow
- API contract (fullstack: fixed here, frontend designs against it)

## Dependencies

- External packages to install
- Internal modules to build on

## Implementation Plan

<!-- From here down, follow ~/.claude/skills/_shared/plan-format.md IN FULL —
with ONE deviation: its `## Phase Status` section lives at the TOP of this file
(above ## Decisions), not here. Everything else is unchanged: vertical phases with
(risk: low|high) tags, per-phase Changes Required + Success Criteria
(Automated/Manual Verification with the project's real commands), Acceptance Stubs
when the ticket has behavioral criteria. This is what /code's phase gates and
/verify consume. Every spec ends with the four mandatory closing phases from
~/.claude/skills/_shared/closing-phases.md (Refactor → Verify → Orient → Recap;
Recap = /branch-recap) — never omitted. -->
```

## Arguments

$ARGUMENTS
