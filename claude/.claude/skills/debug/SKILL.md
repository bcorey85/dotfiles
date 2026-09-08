---
name: debug
description: Systematic debugging — find the root cause before proposing any fix, then route the repair through /fix. Use for any bug, test failure, crash, or unexpected behavior whose cause is NOT yet understood ("why is this failing", "root cause", "/debug"). NOT for applying a fix you already understand (/fix) or scanning your own diff (/review).
---

# Debug — root cause before fix

## The Iron Law

> **NO FIX BEFORE ROOT CAUSE.**

A change at the error surface without knowing why the bad state got there is a symptom patch — it moves the bug.

## When

ANY technical failure: test failure, crash, wrong output, perf regression, flake, build/integration break. **Especially** under time pressure, "simple-looking" bugs, or after a failed fix.

Not this skill:

- You already know the cause and just need the change applied → **/fix**.
- Hunting for bugs in a diff you just wrote → **/review**.
- Traced hard and hit a wall (opaque library error, version mismatch, no visible cause in our code) → **/stop-guessing**. IN-code causes are yours; OUTSIDE-knowledge is theirs.

## Red flags — if you catch yourself here, STOP and return to phase 1

- "Quick fix for now, investigate later" / "it's probably X, let me fix that"
- "Just try changing X and see if it works" / proposing fixes before tracing data flow
- Listing several fixes at once ("here are the main problems: …") without a confirmed cause
- "I don't fully understand it but this might work"
- "One more attempt" — when you have already tried two (see phase 4's architecture rule)

## The four phases — complete each before starting the next

### 1. Reproduce and observe

Get a deterministic repro, read the EXACT failure (full error, stack, exit code — don't skim; it often names the layer). Note observed-vs-expected + **what changed recently** (regressions have a commit). Unreproducible = this phase's whole job; gather data, don't guess.

### 2. Locate the failing layer, then trace to the origin

**Single process, readable call chain** → trace **backward**:

- Start at the failure point: what value or state is wrong right there?
- Walk callers up (LSP, else `rg`), asking per hop: where did the wrong value enter?
- Stop at the **original trigger** (first introduction of bad state) — the root cause, not the crash site.
- Dead-ended → instrument the dangerous op: log suspect value + `new Error().stack` **before** it runs (`console.error` in tests), run once, read the chain.

**Multi-component system** (CI → build → sign, API → service → DB, anything crossing a
process/network/env boundary) → you can't read the chain — **instrument the boundaries**: log in/out + env/config/secrets propagation per boundary. Run **once** to find WHERE it breaks, then investigate only that component.

**Pattern check (both paths):** find a *working* sibling — similar code in the same
codebase that behaves correctly — and list every difference, however small. "That can't matter" is where causes hide.

State the result in one sentence: *"X fails because Y introduces Z at `file:line`."* If
you can't write that sentence, you are not done tracing.

### 3. Confirm before fixing

Form ONE hypothesis, prove with evidence not reasoning (failing assertion at origin, log of bad value, minimal repro). Unconfirmed = still a guess → re-enters phase 2, never proceeds.

### 4. Fix at the source, defended — and know when to stop

- **One change, at the original trigger** — never at the symptom because it's closer, and
  no "while I'm here" refactoring bundled in.
- **Defense in depth** for bad values crossing layers — a check per passed boundary so the *class* becomes impossible:
  - **Entry** — reject invalid input at the API boundary (empty, missing, wrong type).
  - **Business logic** — reject data that doesn't make sense for this operation (mocks
    and alternate code paths bypass entry validation).
  - **Environment guard** — refuse dangerous operations in the wrong context (e.g. no
    destructive writes outside a temp dir under test).
  - **Instrumentation** — log context before the dangerous operation for next time.
- **Route the edit normally**: `/debug` **diagnoses**, `/fix` **repairs** — keep them on their rails so the review gate runs.
- **If the fix doesn't work: count your attempts.** Under 3 → return to phase 1 with the
  new information, form a NEW hypothesis (don't stack fixes). **At 3+, STOP — usually wrong *architecture*, not hypothesis** (tell: each fix reveals fresh coupling). Raise as a design question before fix #4.

## Output

- **Root cause** — one sentence, with the origin `file:line`.
- **Evidence** — what confirmed it (phase 3), not what you suspect.
- **Fix location and shape** — `path:line` plus what change, ready to hand to /fix.
- **Blast radius** — other call paths that reach the same origin and share the bug.

## Boundaries

- Never propose a fix you have not traced to an origin AND confirmed. "Probably" = not done.
- Read-and-trace here; repair goes through the fix path.
- A truly environmental/external cause is a valid finding. Prove it's external before concluding it.
- Phase-2 dead-end outside our code → /stop-guessing; 3+ failures → user as architecture question. Neither licenses more guessing.
