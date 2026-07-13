---
name: eng-spec
description: Spec a feature — goal-blind research first, then architect exploration, then design decisions resolved with you one at a time, then a finalized plan. Auto-detects scope (fe/be/fullstack). Optionally writes the spec to disk and/or dispatches coders.
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

8. **Go lean?** Default is NO — run the architects. Skip Phases 4–6 only if ALL
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
   **still dispatch a coder in Phase 7 if they choose to implement** — the coder
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
    questions), skip Phase 5 and the step-12 finalization; go to Phase 7.

## Phase 5: Interactive design resolution — never batch it

**This is the point of the skill.** Everything else is scaffolding around it.

11. **Present understanding FIRST**, before any decisions: current state, the
    patterns found (ask the user to confirm they are the RIGHT ones to follow),
    constraints, and the architect's **three counter-primed approaches**. The
    user needs a chance to catch a wrong pattern — and to see what was ruled out
    on their behalf — before either propagates into every downstream decision.

12. **Resolve decision points ONE AT A TIME.** Never a batched list. Ask
    follow-ups freely; there is no question quota, and "the conversation feels
    done" is not the completeness test — every decision point and open question
    resolved is. Recommendation first (AskUserQuestion, recommended option
    first), then the alternatives with their real costs.

    **Never resolve a decision by recommending harder. Ask.**

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
    point and open question is resolved.

## Phase 6: Architect finalization

13. **Continue each architect via `SendMessage`** — its exploration context is
    intact, so send only the resolved decision list and the instruction to
    produce the full plan per its Output Format. Do NOT re-litigate resolved
    decisions; they carry the user's authority. If the agent is no longer
    addressable, fall back to a fresh dispatch with its brief verbatim plus the
    resolved decisions.

    **Fullstack ordering**: finalize `backend-architect` first — its plan must
    include a clearly defined **API contract** (endpoints, methods,
    request/response shapes, status codes). Then finalize `frontend-architect`
    *with* that contract, so it designs against it rather than inventing one.

14. **Synthesize the finalized plan(s).**

    - **`DESIGN GAPS` returned by an architect**: resolve each with the user, add
      it to `## Decisions`, **then send the resolution back to that architect**
      and take its revised plan. Its guess may have shaped steps and success
      criteria well past the flagged line; hand-patching the one marked spot
      leaves the rest built on the guess.
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
      contract fixed in step 13 is what makes this safe. A phase stays
      single-layer only when the work genuinely is (migration-only, infra-only).

## Phase 7: User choice

15. **HARD STOP — no spec write, no coder dispatch, until the user answers.**

    Ask both questions in ONE **AskUserQuestion** call ("Save to disk?" and
    "Implement now?"). The blocking modal is the mechanism that makes this stop
    unskippable; asked as prose, it has been skipped before. Presenting the plan
    in conversation is fine. Writing the spec or dispatching coders before the
    answers is NOT.

    **Save to disk?**
    - Yes → Write the spec to `docs/eng-specs/<slug>/spec.md` using the template
      below. The research artifacts stay beside it — they are the evidence the
      decisions were made against.
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

16. **Present summary**: key decisions, file written (if saved), what was
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

```markdown
# Title

> Jira: JIRAPROJECT-TICKETNUMBER (if applicable)
> Research: ./02-research.md (goal-blind, produced before design began)
> Date: YYYY-MM-DD

## Summary

One paragraph on what this accomplishes.

## Decisions

<!-- Every decision uses the four-field block from
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

<!-- From here down, follow ~/.claude/skills/_shared/plan-format.md IN FULL:
## Phase Status with (risk: low|high) tags, vertical phases, per-phase Changes
Required + Success Criteria (Automated/Manual Verification with the project's
real commands), Acceptance Stubs when the ticket has behavioral criteria. This is
what /code's phase gates and /verify consume. Every spec ends with the four
mandatory closing phases from ~/.claude/skills/_shared/closing-phases.md
(Refactor → Verify → Orient → Finalize; Finalize = /adr) — never omitted. -->
```

## Arguments

$ARGUMENTS
