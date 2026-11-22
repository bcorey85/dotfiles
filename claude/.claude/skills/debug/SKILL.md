---
name: debug
description: Find the root cause of a bug, test failure, crash or unexpected behavior whose cause is not yet known, then hand the repair to /fix. Use for "why is this failing", "root cause". A known cause goes straight to /fix.
---

# Debug — root cause before fix

A change at the error surface without knowing why the bad state got there is a **symptom patch**: it moves the bug. Find the root cause first.

## When

Any technical failure: test failure, crash, wrong output, perf regression, flake, build or integration break. Especially under time pressure, on a "simple-looking" bug, or after a failed fix.

Routing:

- Cause already known, change only needs applying → **/fix**.
- Hunting for bugs in a diff you just wrote → **/review**.
- Traced hard and hit a wall outside our code (opaque library error, version mismatch) → WebSearch the exact error and versions and cite the sources. In-code causes come from tracing; outside knowledge comes from sources.

A fix proposed before the cause is confirmed (one guess, or a list of several) sends you back to phase 1.

## The four phases, in order

### 1. Reproduce and observe

Get a deterministic repro and read the exact failure: full error, stack, exit code. Note observed vs expected and **what changed recently** (a regression has a commit). Done when one command fails the same way twice. When it will not reproduce, gather data until the data names a layer.

### 2. Locate the failing layer, then trace to the origin

**Single process, readable call chain** → trace **backward**:

- Start at the failure point: what value or state is wrong right there?
- Walk callers up, asking at each hop: where did the wrong value enter?
- Stop at the **original trigger** (first introduction of bad state): the root cause, not the crash site.
- Dead-ended → log the suspect value and a stack trace just before the dangerous op, run once, read the chain.

**Multi-component system** (CI → build → sign, API → service → DB, anything crossing a process, network or env boundary) → **instrument the boundaries**: log in/out and env/config/secret propagation at each one. Run **once** to find where it breaks, then investigate only that component.

**Pattern check (both paths):** find a working sibling (similar code in the same codebase that behaves correctly) and list every difference, however small.

Done when you can state: _"X fails because Y introduces Z at `file:line`."_

### 3. Confirm before fixing

Form ONE hypothesis and prove it with evidence: a failing assertion at the origin, a log of the bad value, a minimal repro. An unconfirmed hypothesis returns to phase 2.

### 4. Fix at the source, defended

- **One change, at the original trigger**, with nothing else bundled in.
- Where the bad value crossed layers, add a check at each boundary it passed, so the class cannot recur.
- `/debug` **diagnoses**, `/fix` **repairs**: hand the fix to /fix so the review gate runs.
- **Count attempts.** A failed fix under 3 attempts → back to phase 1 with the new information and a NEW hypothesis. **At 3, STOP**: the architecture is usually wrong (each fix reveals fresh coupling). Raise it with the user as a design question.

## Output

- **Root cause** — one sentence, with the origin `file:line`.
- **Evidence** — what confirmed it (phase 3).
- **Fix location and shape** — `path:line` plus what change, ready to hand to /fix.
- **Blast radius** — other call paths that reach the same origin and share the bug.

An environmental or external cause is a valid finding once you prove it is external.
