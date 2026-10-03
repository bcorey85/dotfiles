---
name: test-audit
description: The cross-phase test gate — the half of test-intent no single phase can judge. Cull test spam, sweep weak/absent assertions against the plan, all at branch scope. Use for "test audit", "cross-phase test audit", "/test-audit". The third closing phase, a gate — it routes findings to /fix and hands its receipt to /branch-recap.
allowed-tools: [Bash, Read, Glob, Grep, Agent, Skill]
---

# Test audit — the cross-phase test gate

The third closing phase — the one test question no phase answers locally: do the branch's tests, taken whole, pin intent without spam or loose oracles? Bug-pinning is not run here. Cull + weak only.

Output: findings to `/fix`, a flywheel log row, a receipt line for `/branch-recap`.

## The audit

Dispatch `test-intent-reviewer` (pinned; omit `model`) — **cull + weak scope** (`scope: cull` in its contract).

Hand it branch diff + oracle (spec + AC). Cull and WEAK findings → `/fix`. Then run the execution gate once, after the last change, unless that change came through `/fix`: its loop already ran the gate.

**`REQUIRES-MUTATION` → `mutation-tester`, not `/fix`.** Dispatch with the named mutation (pinned; omit `model`); resolve the cull only after. Never resolve by judgement — unrouted stays open and reported open. Several → dispatch SEQUENTIALLY (global lock; concurrent runs abort).

Verdicts are defined in `mutation-tester.md` — read them there, never restate. Only KILLED (test earns its place) and SURVIVED (cull stands) settle the cull. The other two misread as:

- **EQUIVALENT** is not a survivor. The mutant is unobservable, so the cull question was
  malformed and no test could ever settle it. Do **not** commission coverage to chase it.
- **INDETERMINATE** is still open. Report it open; do not downgrade it to a pass.

Receipt line (hand to `/branch-recap`): `test audit: <n> culled, <n> weak of <N> plan promises walked | clean | skipped — no test files`.

## Logging

Log the firing (non-blocking; skip if audit skipped):

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" \
  repo="$(basename "$(git rev-parse --show-toplevel)")" lane=test-audit \
  test_intent_ran=1 test_intent=<n findings> tests_added=<the auditor's Tests added header> culled=<n> weak=<n> \
  requires_mutation=<n> mutation_equivalent=<n of those the tester ruled EQUIVALENT> \
  mutation_open=<n still INDETERMINATE or unrouted> \
  result=<clean|findings>
```

Then per-finding rows per `~/.claude/skills/_shared/finding-log.md` (read it): `gate=test-intent-reviewer lane=test-audit scope=branch-exit`. Zero-finding audits still log `kind=run`.

## What NOT to do

- **Never edit code or tests** — findings route to `/fix`; this phase dispatches.
- **Never `git add`, commit, or open a PR** — residue + recap are `/branch-recap`'s.
- **No bug-pinning half** — `scope: cull` only.

## Arguments

$ARGUMENTS
