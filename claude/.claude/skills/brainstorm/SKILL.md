---
name: brainstorm
description: Vet a rough idea into a correct Jira ticket for a teammate. Use when the user wants to think through an issue before filing it, or says "brainstorm", "write this up for the team", "is this ticket right". Verifies the premise against the real codebase, resolves the approach, then hands off to /create-ticket. Do NOT use for work about to be planned or implemented here — /eng-spec INGESTS tickets; this skill PRODUCES them.
allowed-tools: [Bash, Read, Glob, Grep, AskUserQuestion, Skill]
---

# Brainstorm — vet a ticket before it costs a teammate rework

This skill exists to make the ticket NOT WRONG — every
factual claim verified, the approach feasible, the acceptance unambiguous.

## Steps

### 1. Gather intent

Take the problem as described. Epic link/key passes straight to `/create-ticket` (`parent`); no epic means backlog ticket, do not ask.

### 2. Verify the premise — before designing anything

Check assumed facts against the repo (behavior really happens? code still works that way? thing already exists?). Cite `file:line` per load-bearing fact. Wrong premise means say so; a killed ticket is a success.

This reading is **verification**, not scoping — `/create-ticket` owns file-naming.

### 3. Clarify — one question at a time

**First question, always: appetite** (quick fix? days? week?). Appetite starts with a number and ends with a design — it constrains every fork.

Then serial multiple-choice questions (purpose, constraints, done). Stop when Work plus Acceptance write without hedging.

### 4. Resolve the approach

Real forks mean 2–3 approaches plus trade-offs plus recommendation, YAGNI ruthlessly. One way means skip ceremony. Ecosystem questions go to `/research` (its Alternatives table drops into Technical Notes).

### 5. Vet gate — the point of the skill

Walk the draft before filing. Every item must pass:

- [ ] Every factual claim was checked against the repo **this session** — nothing rests on memory or the user's recollection alone
- [ ] The approach doesn't collide with an existing pattern, constraint, or in-flight change you can see
- [ ] Acceptance criteria are testable by someone who wasn't in this conversation
- [ ] No unanswered question is buried as an assumption — each goes to `## Open Questions` with a named owner
- [ ] YAGNI pass: nothing in scope that the stated purpose doesn't require
- [ ] Fits the appetite — ballooned past it means split or renegotiate; never file bigger than the problem is worth

Anything failing → back to steps 2–4, don't file around it.

### 6. File via /create-ticket

Hand off: outcome plus verified constraints go to `## Work` (appetite as one line, e.g. `Appetite: ~2 days`), done-criteria go to `## Acceptance`, resolved approach goes to Technical Notes as recommendation, rejected plus evidence go to Technical Notes, unknowns go to Open Questions. Pass epic through.

Pin the WHAT; recommend the HOW. Only promote the approach into `## Work`
when deviating from it would violate a constraint you verified.

Multiple independent pieces means ask ONCE: one ticket (deferred go to Out of scope); one ticket per piece under the epic (vertical slices, never by layer); or file only the first slice when genuinely uncertain (building rewrites the rest).

## Boundaries

- Produces tickets only — never plans, coders, or `/eng-spec`.
- Read-only against the repo.
- If Jira/`/create-ticket` is unavailable, deliver the vetted brief inline for manual filing.
