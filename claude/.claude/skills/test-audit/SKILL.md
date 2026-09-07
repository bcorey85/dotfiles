---
name: test-audit
description: The cross-phase test gate — the half of test-intent no single phase can judge. Cull test spam, catch net-removed coverage, sweep weak/absent assertions against the plan, all at branch scope. Use for "test audit", "cross-phase test audit", "/test-audit". The third closing phase, a gate — it routes findings to /fix and test-writer, and hands its receipt to /branch-recap.
allowed-tools: [Bash, Read, Glob, Grep, Agent, Skill]
---

# Test audit — the cross-phase test gate

The third closing phase — the one test question no phase answers locally: do the branch's tests, taken whole, pin intent without spam, lost coverage, or loose oracles? Bug-pinning is severed by the coder/test-writer split; not run here. Cull + coverage-net + weak only.

Output: findings to `/fix` (cull/coverage) or `test-writer` re-dispatch (weak), a flywheel log row, a receipt line for `/branch-recap`.

## The audit

Dispatch `test-intent-reviewer` (pinned; omit `model`) — **cull + coverage-net + weak
scope** (`scope: cull` in its contract).

Hand it branch diff + oracle (spec + AC). Cull/coverage → `/fix`; WEAK → `test-writer` re-dispatch (implementation-blind). Then re-run the execution gate. Net-removed coverage tops the recap's read-first queue.

**`REQUIRES-MUTATION` → `mutation-tester`, not `/fix`.** Dispatch with the named mutation (pinned; omit `model`); resolve the cull only after. Never resolve by judgement — unrouted stays open and reported open. Several → dispatch SEQUENTIALLY (global lock; concurrent runs abort).

Verdicts are defined in `mutation-tester.md` — read them there, never restate. Only KILLED (test earns its place) and SURVIVED (cull stands) settle the cull. The other two misread as:

- **EQUIVALENT** is not a survivor. The mutant is unobservable, so the cull question was
  malformed and no test could ever settle it. Do **not** commission coverage to chase it.
- **INDETERMINATE** is still open. Report it open; do not downgrade it to a pass.

**Denominator into the receipt — bare `0` is not a result.** Empty branch-point set (greenfield, testless base) can't fail; its pass is byte-identical to no-op. Take the auditor's `Base suite at branch point` header verbatim.

Receipt line (hand to `/branch-recap`): `test audit: <n> culled, <n> coverage-lost of <m> pre-existing tests searched, <n> weak | coverage-net N/A — base suite empty | clean | skipped — no test files`.

## Logging

Log the firing (non-blocking; skip if audit skipped):

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" \
  repo="$(basename "$(git rev-parse --show-toplevel)")" lane=test-audit \
  test_intent_ran=1 test_intent=<n findings> culled=<n> coverage_lost=<n> weak=<n> \
  base_suite=<m pre-existing tests searched; 0 means the coverage-net gate did not run> \
  requires_mutation=<n> mutation_equivalent=<n of those the tester ruled EQUIVALENT> \
  mutation_open=<n still INDETERMINATE or unrouted> \
  result=<clean|findings>
```

Then per-finding rows per `~/.claude/skills/_shared/finding-log.md` (read it): `gate=test-intent-reviewer lane=test-audit scope=branch-exit`. Zero-finding audits still log `kind=run`.

## What NOT to do

- **Never edit code or tests** — findings route to `/fix` / `test-writer`; this phase dispatches.
- **Never `git add`, commit, or open a PR** — residue + recap are `/branch-recap`'s.
- **No bug-pinning half** — `scope: cull` only.

## Arguments

$ARGUMENTS
