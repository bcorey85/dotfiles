---
name: test-audit
description: The cross-phase test gate: culls test spam and sweeps weak or absent assertions against the plan at branch scope; routes findings to /fix, hands its receipt to /branch-recap. `review [be|fe|fs|branch] [focus]` instead reviews a test suite for coverage gaps, weak assertions and stale tests. Use for "test audit", "review the tests", "test suite health", "coverage check", "cull the branch's tests".
allowed-tools: [Bash, Read, Glob, Grep, Agent, Skill]
---

# Test audit — the cross-phase test gate

The third closing phase — the one test question no phase answers locally: do the branch's tests, taken whole, pin intent without spam or loose oracles? Bug-pinning is not run here. Cull + weak only.

If `$ARGUMENTS` starts with `review`, run **Review mode** below and skip the rest. Otherwise run the audit.

Output: findings to `/fix`, a flywheel log row, a receipt line for `/branch-recap`.

## The audit

Dispatch `test-intent-reviewer` (pinned; omit `model`) — **cull + weak scope** (`scope: cull` in its contract).

Hand it branch diff + oracle (spec + AC). Cull and WEAK findings → `/fix`, with `lane: test-audit` in its args. Then run the execution gate once, after the last change, unless that change came through `/fix`: its loop already ran the gate.

**`REQUIRES-MUTATION` → `mutation-tester`, not `/fix`.** Dispatch with the named mutation (pinned; omit `model`); resolve the cull only after. Never resolve by judgement — unrouted stays open and reported open. Several → dispatch SEQUENTIALLY (global lock; concurrent runs abort).

Verdicts are defined in `mutation-tester.md` — read them there, never restate. Only KILLED (test earns its place) and SURVIVED (cull stands) settle the cull. The other two misread as:

- **EQUIVALENT** is not a survivor. The mutant is unobservable, so the cull question was
  malformed and no test could ever settle it. Do **not** commission coverage to chase it.
- **INDETERMINATE** is still open. Report it open; do not downgrade it to a pass.

Receipt line (hand to `/branch-recap`): `test audit: <n> culled, <n> weak of <N> plan promises walked | clean | skipped — no test files`.

## Logging

Log the firing (non-blocking; skip if audit skipped):

```bash
~/.claude/skills/review/log-review-metrics \
  lane=test-audit \
  test_intent_ran=1 test_intent=<n findings> tests_added=<the auditor's Tests added header> culled=<n> weak=<n> \
  requires_mutation=<n> mutation_equivalent=<n of those the tester ruled EQUIVALENT> \
  mutation_open=<n still INDETERMINATE or unrouted> \
  result=<clean|findings>
```

Then per-finding rows per `~/.claude/skills/_shared/finding-log.md` (read it): `gate=test-intent-reviewer lane=test-audit scope=branch-exit`. Zero-finding audits still log `kind=run`.

- The finding-log `kind=run` row passes `diff_base=<the base ref of the branch diff>`, never `diff_loc=`. The metrics row above takes no diff field. The script measures the branch and the working tree, so the audit's uncommitted fixes count.
- Each finding row passes the test `file=` and `line=` the auditor's finding names. A finding that names only a plan promise, such as an `absent` WEAK, passes `file=unlocated` and no line. Never guess a file.

## Review mode: `review [be|fe|fs|branch] [focus]`

Ad-hoc suite review, off the closing pipeline. Dispatch `test-reviewer` (omit `model`; frontmatter pins Sonnet).

1. Take the modifier: `be`/`backend`, `fe`/`frontend`, `fs`/`fullstack` or `branch`. Any text after it is a focus area passed to the agent.
2. With no modifier, classify the diff and untracked files as fe or be per the project layout (CLAUDE.md if unclear): only fe is `frontend`, only be is `backend`, both is `fullstack`, ambiguous means ask.
3. Dispatch `frontend` or `backend` as one agent, `fullstack` as two in parallel. `branch` is one agent with scope `branch` (it diffs the merge-base itself) and reviews only branch-added or modified tests plus a cull check. Never run `branch` on a pipeline branch: this audit already judges those tests.
4. Present the report and ask about dispatching coders for fixes. Log nothing.

## What NOT to do

- **Never edit code or tests** — findings route to `/fix`; this phase dispatches.
- **Never `git add`, commit, or open a PR** — residue + recap are `/branch-recap`'s.
- **No bug-pinning half** — `scope: cull` only.

## Arguments

$ARGUMENTS
