---
name: test-audit
description: The cross-phase test gate — the half of test-intent no single phase can judge. Cull test spam, catch net-removed coverage, sweep weak/absent assertions against the plan, all at branch scope. Use for "test audit", "cross-phase test audit", "/test-audit". The third closing phase, a gate — it routes findings to /fix and test-writer, and hands its receipt to /branch-recap.
allowed-tools: [Bash, Read, Glob, Grep, Agent, Skill]
---

# Test audit — the cross-phase test gate

The third closing phase, and a gate. It runs the one test question no phase can
answer locally: whether the branch's tests, taken as a whole, pin intended behavior
without spam, without lost coverage, and without loose oracles.

Bug-pinning is structurally severed by the coder/test-writer split and its hooks; it
does not run here. This phase is cull + coverage-net + weak only.

Output: findings routed to `/fix` (cull/coverage) or a `test-writer` re-dispatch
(weak), a machine log to the review flywheel, and a receipt line the `/branch-recap`
synthesis consumes.

## The audit

Dispatch `test-intent-reviewer` (pinned; omit `model`) — **cull + coverage-net + weak
scope** (`scope: cull` in its contract).

This half of the audit is inherently cross-phase and cannot be done phase-locally:

- **Test spam** — phase 2 and phase 4 each adding a test for the same behavior is
  invisible from inside either phase.
- **`COVERAGE-LOST`** — a test deleted in phase 1 and legitimately replaced in phase 3
  looks like lost coverage at phase 1, and only resolves when both are in view.
- **`WEAK`** — under-pinned and absent assertions against the plan's promises. Runs here
  and not at phase scope: the class that leaks is absent assertions and cross-phase
  artifacts, visible only with the whole suite and whole plan in view. WEAK findings
  route to a `test-writer` re-dispatch, not `/fix`.

Hand it the branch diff (`git diff <base>...HEAD`) and the oracle (spec + acceptance
criteria). Cull/coverage findings route through `/fix`; WEAK findings route to a
`test-writer` re-dispatch (implementation-blind). Then re-run the loop's execution gate.
Net-removed coverage goes to the top of the read-first queue the recap will assemble.

**`REQUIRES-MUTATION` findings route to `mutation-tester`, not to `/fix`.** The
auditor is read-only and will return this class whenever a cull decision cannot be
settled by reading. Dispatch `mutation-tester` (pinned; omit `model`) with the named
mutation, and only then resolve the cull. Never resolve one of these by judgement —
an unrouted `REQUIRES-MUTATION` stays open and is reported as open. With several to
settle, dispatch them SEQUENTIALLY — the mutation lock is global, so a second
concurrent run aborts on the first one's lock even in a different repo.

It returns one of four verdicts, defined with their preconditions in
`~/.claude/agents/mutation-tester.md` — read them there rather than from a summary, and
never restate them in a prompt that produces a verdict rather than reads one. Only two of
the four settle the cull: KILLED means the test earns its place, SURVIVED means the cull
argument stands. The other two are results, not failures to reach one, and each has a way
of being misread here:

- **EQUIVALENT** is not a survivor. The mutant is unobservable, so the cull question was
  malformed and no test could ever settle it. Do **not** commission coverage to chase it —
  a test written against an equivalent mutant asserts nothing, which is how vacuous tests
  get added by a process meant to remove them.
- **INDETERMINATE** is still open. Report it open; do not downgrade it to a pass.

**Carry the denominator into the receipt — a bare `0` is not a result here.** The
coverage-net check searches the tests that existed at the branch point; when that set
is empty (greenfield branch, or a base with no tests) the check cannot fail, and its
pass is byte-identical to its no-op. Take the auditor's `Base suite at branch point`
header verbatim.

Receipt line (hand to `/branch-recap`): `test audit: <n> culled, <n> coverage-lost of <m> pre-existing tests searched, <n> weak | coverage-net N/A — base suite empty | clean | skipped — no test files`.

## Logging

Log the firing to the review flywheel (non-blocking; on failure mention and continue; skip if the audit was skipped):

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" \
  repo="$(basename "$(git rev-parse --show-toplevel)")" lane=test-audit \
  test_intent_ran=1 test_intent=<n findings> culled=<n> coverage_lost=<n> weak=<n> \
  base_suite=<m pre-existing tests searched; 0 means the coverage-net gate did not run> \
  requires_mutation=<n> mutation_equivalent=<n of those the tester ruled EQUIVALENT> \
  mutation_open=<n still INDETERMINATE or unrouted> \
  result=<clean|findings>
```

Then emit the per-gate and per-finding rows per
`~/.claude/skills/_shared/finding-log.md` (read it) with
`gate=test-intent-reviewer lane=test-audit scope=branch-exit`. A zero-finding
audit still logs its `kind=run` row.

## What NOT to do

- **Never edit code, never edit a test** — cull/coverage findings route through `/fix`,
  weak findings route to a `test-writer` re-dispatch. This phase dispatches; it does not
  author.
- **Never `git add`, never commit, never open a PR** — residue staging and the recap are
  `/branch-recap`'s job, the phase after this one.
- **Do not run the bug-pinning half** — `scope: cull` only, per the reviewer's contract.

## Arguments

$ARGUMENTS
