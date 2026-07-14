---
name: brainstorm
description: Vet a rough idea into a correct Jira ticket for a teammate. Use when the user wants to think through an issue before filing it, or says "brainstorm", "write this up for the team", "is this ticket right". Verifies the premise against the real codebase, resolves the approach, then hands off to /create-ticket. Do NOT use for work about to be planned or implemented here — /eng-spec INGESTS tickets; this skill PRODUCES them.
allowed-tools: [Bash, Read, Glob, Grep, AskUserQuestion, Skill]
---

# Brainstorm — vet a ticket before it costs a teammate rework

A ticket crosses a person boundary and a time boundary. The implementer wasn't
in this conversation and starts weeks later. Anything wrong in the ticket
becomes their rework. This skill exists to make the ticket NOT WRONG — every
factual claim verified, the approach feasible, the acceptance unambiguous.

## Steps

### 1. Gather intent

Take the problem as described. If an epic link/key is given, hold it — it
passes straight through to `/create-ticket` (which handles `parent`). No epic
means the ticket goes to the backlog; that's fine, don't ask about it.

### 2. Verify the premise — before designing anything

The #1 rework cause is a stale premise. Check the assumed facts against the
actual repo: does the described behavior really happen, does the code still
work the way the request assumes, does the thing being asked for already
exist? Cite `file:line` for each load-bearing fact. If the premise is wrong,
say so — a killed ticket is a success, not a failure.

This reading is for **verification** (what's true, what constrains the
approach) — not scoping. `/create-ticket` owns naming files in the ticket.

### 3. Clarify — one question at a time

**First question, always: the appetite.** How much is this problem worth —
a quick fix, a couple of days, a week? An appetite starts with a number and
ends with a design (not the reverse); it constrains every fork downstream
and does more to prevent gold-plating than trimming scope at the end.

Then serial questions, multiple choice preferred: purpose, constraints, what
done looks like. Stop when `## Work` and `## Acceptance` could be written
without hedging — that's the completeness test, not "the conversation feels
done."

### 4. Resolve the approach

Where a real fork exists, propose 2–3 approaches with trade-offs and a
recommendation; apply YAGNI ruthlessly. Skip the ceremony when there's
genuinely one way. Ecosystem/library questions go to `/research` — its
Alternatives Considered table drops into the ticket's Technical Notes.

### 5. Vet gate — the point of the skill

Walk the draft before filing. Every item must pass:

- [ ] Every factual claim was checked against the repo **this session** — nothing rests on memory or the user's recollection alone
- [ ] The approach doesn't collide with an existing pattern, constraint, or in-flight change you can see
- [ ] Acceptance criteria are testable by someone who wasn't in this conversation
- [ ] No unanswered question is buried as an assumption — each goes to `## Open Questions` with a named owner
- [ ] YAGNI pass: nothing in scope that the stated purpose doesn't require
- [ ] The work fits the appetite — plausibly lands in days, not weeks. If scoping ballooned past it, split or renegotiate the appetite; never file a ticket bigger than what the problem is worth

Anything failing → back to steps 2–4, don't file around it.

### 6. File via /create-ticket

Hand off a structured brief: **outcome + verified constraints** → `## Work`
(with the appetite as one line, e.g. `Appetite: ~2 days` — the timebox is
what pushes the implementer to decide core vs peripheral), done-criteria →
`## Acceptance`, the resolved approach → `## Technical Notes` as a
_recommendation_, rejected approaches + verification evidence →
`## Technical Notes`, unknowns → `## Open Questions`. Pass the epic link
through if one was given.

Pin the WHAT; recommend the HOW. Only promote the approach into `## Work`
when deviating from it would violate a constraint you verified — a mandated
approach turns the implementer's judgment off, and a flawed one gets
followed instead of flagged.

If the work turned out to be multiple independent pieces, ask ONCE, offering
three options: keep it one ticket (deferred pieces → `## Out of scope`);
one `/create-ticket` per piece under the same epic — each piece a vertical
slice, observably valuable on its own, never split by layer; or, when the
problem is genuinely uncertain, file only the first slice — building it will
rewrite the design for the rest. Nothing else — no linking, no sequencing.

## Boundaries

- Produces tickets; never plans implementation, never dispatches coders, never invokes `/eng-spec`.
- Read-only against the repo.
- If Jira/`/create-ticket` is unavailable, deliver the vetted brief inline for manual filing.
