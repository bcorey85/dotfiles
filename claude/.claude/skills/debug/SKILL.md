---
name: debug
description: Structured root-cause investigation — reproduce, gather evidence, rank hypotheses, verify the cause before any fix. Read-only; produces a diagnosis to hand to /fix or /code. Use when something is broken and the cause is unknown ("why is X failing", "this broke", "getting this error"). If repeated fix attempts have already failed, use /stop-guessing instead.
---

# Debug

Find the cause before anyone touches a fix. This skill is read-only — it ends with a diagnosis, not an edit. Its job is to make /stop-guessing unnecessary.

## Process

### 1. Reproduce

Pin down the exact failing command, input, and error. Run it ONCE, redirected to `/tmp/debug.log`, and grep the log for different views — never re-run to see different parts of the output.

If you cannot reproduce it, say so and ask the user for the trigger. Do NOT diagnose from a description alone.

### 2. Evidence before theories

- Read the error trace bottom-up; find the deepest frame in project code (`file:line`) — not framework code.
- `git log --oneline -15 -- <implicated files>` — "what changed recently" beats "what looks wrong".
- Read the implicated code and its callers (LSP find-references for typed code).

### 3. Hypotheses (max 3, ranked)

One line each: **cause → mechanism → cheapest discriminating check**. Rank by prior probability (recent changes first, then config/environment, then long-standing code).

### 4. Verify the top hypothesis

Confirm with evidence — a log line, a minimal repro, a type check, a value inspected at the boundary. NEVER verify by applying the candidate fix to see if the problem goes away.

If disproven, move to the next hypothesis. If all 3 die, stop and run `/research` with the exact error message and versions — or `/stop-guessing` if fixes were already attempted.

### 5. Diagnosis report

```
## Diagnosis

**Cause**: <one sentence> — `file:line`
**Mechanism**: <how it produces the observed failure>
**Evidence**: <the chain that confirms it>
**Suggested fix**: <what to change, with blast radius — callers/consumers affected>
**Confidence**: high / medium / low
```

Then offer to dispatch `/fix` (or `/code` if the fix is bigger than a patch). Do NOT implement the fix directly.

## Rules

- Read-only. No edits, no "quick fixes while we're here".
- One reproduction run; grep `/tmp/debug.log` after.
- Max 3 hypotheses before escalating to `/research` or `/stop-guessing`.
- A diagnosis with low confidence and honest gaps beats a confident guess.

## Arguments

$ARGUMENTS
