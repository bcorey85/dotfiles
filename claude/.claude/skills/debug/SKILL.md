---
name: debug
description: Systematic debugging — find the root cause before proposing any fix, then route the repair through /fix. Use for any bug, test failure, crash, or unexpected behavior whose cause is NOT yet understood ("why is this failing", "root cause", "/debug"). NOT for applying a fix you already understand (/fix) or scanning your own diff (/review).
---

# Debug — root cause before fix

## The Iron Law

> **NO FIX BEFORE ROOT CAUSE.**

A change at the point the error surfaces, made without knowing why the bad value or
state got there, is a symptom patch. It moves the bug; it does not remove it. Every
fix you have tried that didn't hold is the signal that you skipped this.

## When

Use for ANY technical failure: test failure, crash, wrong output, performance
regression, flaky test, build break, integration break. **Especially** under time
pressure, when the bug "looks simple," or when a previous fix didn't take — simple
bugs have root causes too, and rushing guarantees rework.

Not this skill:

- You already know the cause and just need the change applied → **/fix**.
- Hunting for bugs in a diff you just wrote → **/review**.
- You have traced hard and hit a wall — an opaque library error, a version mismatch,
  behavior with no visible cause in our code → **/stop-guessing** (external research).
  This skill finds causes that live IN the code; stop-guessing finds causes that live
  OUTSIDE your knowledge. Escalate at the boundary; don't thrash.

## Red flags — if you catch yourself here, STOP and return to phase 1

- "Quick fix for now, investigate later" / "it's probably X, let me fix that"
- "Just try changing X and see if it works" / proposing fixes before tracing data flow
- Listing several fixes at once ("here are the main problems: …") without a confirmed cause
- "I don't fully understand it but this might work"
- "One more attempt" — when you have already tried two (see phase 4's architecture rule)

Each of these is the thought that precedes a symptom patch. Naming it is how you stop it.

## The four phases — complete each before starting the next

### 1. Reproduce and observe

Get a deterministic repro, then read the EXACT failure — full error, full stack, exit
code. Read it, don't skim it: the message often names the failing layer outright. Note
what you actually observe versus what you expected, and **what changed recently** (git
diff, new deps, config, environment) — regressions have a commit. If you can't
reproduce it, that is this phase's whole job; gather more data, don't start guessing.

### 2. Locate the failing layer, then trace to the origin

**Single process, readable call chain** → trace **backward**:

- Start at the failure point. What value or state is wrong right there?
- Walk each caller up the chain — LSP find-references where the language has a server,
  fall back to `rg` — asking at each hop: where did this wrong value enter? A wrong
  path, a null, a stale config, an unvalidated input, a mutation two frames up.
- Stop at the **original trigger**: the first place the bad state was introduced. That
  is the root cause — not the crash site where it finally became visible.
- If manual tracing dead-ends, instrument the dangerous operation itself: log the
  suspect value plus `new Error().stack` **before** it runs (in tests use `console.error`,
  not a logger that may be suppressed), run once, read the captured chain.

**Multi-component system** (CI → build → sign, API → service → DB, anything crossing a
process/network/env boundary) → you often can't read the chain, so **instrument the
boundaries** instead of guessing which one broke:

- At each component boundary, log what data enters and what exits, and whether
  environment/config/secrets propagated across it.
- Run **once** to gather evidence showing WHERE it breaks (secrets → workflow ✓,
  workflow → build ✗), then investigate only that component.

**Pattern check (both paths):** find a *working* sibling — similar code in the same
codebase that behaves correctly — and list every difference, however small. "That can't
matter" is where root causes hide.

State the result in one sentence: *"X fails because Y introduces Z at `file:line`."* If
you can't write that sentence, you are not done tracing.

### 3. Confirm before fixing

Form ONE hypothesis: *"I think X is the root cause because Y."* Prove it with evidence,
not reasoning — a failing assertion at the origin, a log showing the bad value at that
point, a minimal repro test. A theory you have not confirmed is still a guess, and a
guess re-enters phase 2; it does not proceed to a fix.

### 4. Fix at the source, defended — and know when to stop

- **One change, at the original trigger** — never at the symptom because it's closer, and
  no "while I'm here" refactoring bundled in.
- **Defense in depth** for a bad value that crossed layers — add a check at each boundary
  it passed so the whole *class* of bug becomes structurally impossible, not just this
  instance. The four layers, each catching what the others miss:
  - **Entry** — reject invalid input at the API boundary (empty, missing, wrong type).
  - **Business logic** — reject data that doesn't make sense for this operation (mocks
    and alternate code paths bypass entry validation).
  - **Environment guard** — refuse dangerous operations in the wrong context (e.g. no
    destructive writes outside a temp dir under test).
  - **Instrumentation** — log context before the dangerous operation for next time.
- **Route the edit your normal way**: **/fix** (coder dispatch) in a dispatch repo, a
  direct edit in a direct-edit repo. In any non-trivial repo, `/debug` **diagnoses** and
  `/fix` **repairs** — keep them on their normal rails so the review gate still runs.
- **If the fix doesn't work: count your attempts.** Under 3 → return to phase 1 with the
  new information, form a NEW hypothesis (don't stack fixes). **At 3+ failed fixes, STOP —
  this is usually a wrong *architecture*, not a wrong hypothesis:** the tell is that each
  fix reveals fresh coupling or spawns a new symptom elsewhere. Raise it with the user as
  a design question before attempting fix #4.

## Output

- **Root cause** — one sentence, with the origin `file:line`.
- **Evidence** — what confirmed it (phase 3), not what you suspect.
- **Fix location and shape** — where, and what change, ready to hand to /fix.
- **Blast radius** — other call paths that reach the same origin and share the bug.

## Boundaries

- Never propose a fix you have not traced to an origin AND confirmed. "Probably" = not done.
- Read-and-trace here; the repair goes through the normal fix path so nothing skips review.
- A truly environmental/external cause is a valid finding — but 95% of "no root cause"
  is incomplete investigation. Prove it's external before concluding it.
- Phase 2 dead-ending on a cause outside our code is the hand-off to /stop-guessing;
  3+ failed fixes is the hand-off to the user as an architecture question. Neither is a
  licence to keep guessing.
