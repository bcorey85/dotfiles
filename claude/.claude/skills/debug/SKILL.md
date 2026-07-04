---
name: debug
description: Structured debugging workflow — reproduce, isolate, hypothesize, verify. Read-only diagnosis first; no fixes until the root cause is demonstrated. Use when something is broken and the cause isn't obvious.
allowed-tools: [Bash, Read, Glob, Grep, LSP, Skill]
---

# Debug

Diagnose a bug methodically instead of guess-editing. The deliverable of this skill is a **demonstrated root cause**, not a fix — fixing happens afterwards (directly in direct-edit repos, via `/code` elsewhere) once the diagnosis is confirmed.

## Hard rules

- **Read-only until root cause.** No file edits during diagnosis. Adding temporary instrumentation (a log line, a breakpoint script) is allowed only if you announce it and remove it before finishing.
- **One hypothesis at a time.** Never apply two speculative changes together — you learn nothing from the outcome.
- **3-strike circuit breaker.** If 3 hypotheses in a row are disproven, STOP and invoke `/stop-guessing` — you're pattern-matching, not reasoning. Do not silently start a fourth.

## Workflow

1. **Capture the failure precisely.** From the arguments and conversation: exact error message / wrong behavior, expected behavior, and when it last worked (if known). If the report is vague ("it's broken"), ask for the observable symptom before anything else.

2. **Reproduce it.** Find the smallest command or interaction that triggers the failure and run it, capturing output to `/tmp/debug-repro.log`. If you cannot reproduce it, say so and stop — debugging an unreproducible failure is guessing by definition. (Exception: post-mortem log analysis when the user says reproduction isn't possible — then the logs are your only evidence, treat them as the reproduction.)

3. **Isolate.** Narrow the failure surface before hypothesizing:
   - `git log --oneline -15` and `git diff HEAD~5 --stat` if this recently worked — a regression usually lives in a recent diff.
   - Binary-search the path: does the bad value exist at the API boundary? At the service layer? At the DB? Find the last point where state is correct and the first where it's wrong.
   - Check the boring causes first: environment (versions, env vars, stale build/cache), config, data shape — before suspecting logic.

4. **Hypothesize explicitly.** State: "Hypothesis N: <cause>. If true, then <specific observable prediction>." The prediction must be checkable by reading code, running the repro, or inspecting state — not "the fix will work".

5. **Verify or kill it.** Run the check. Disproven → record it ("H1: dead — <evidence>") and return to step 3 or 4 with what you learned. Confirmed → demonstrate it: show the exact line(s), the mechanism, and why it produces exactly the observed symptom (not just "could be related").

6. **Report the diagnosis**: root cause with `file:line`, the causal chain from that line to the symptom, the evidence, and the proposed fix (one or more options if there's a real tradeoff). Then stop — apply the fix only when the user confirms, per the assessment-first rule, unless they already asked for the fix up front.

## Arguments

$ARGUMENTS
