---
name: branch-recap
description: The final closing phase — reassemble a gated branch into one thing you can hold in your head before the PR. Cross-phase test audit, closing-phase residue triage, and a recap receipt. Use for "recap", "branch recap", "wrap up the branch", "/branch-recap". Hands back a read queue — the staging and the commit stay the user's.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Branch recap

The fourth and last closing phase, and the exit-side counterpart to `/eng-spec`.

**It is not a gate.** By the time you reach it every gate has already fired, and fired
where its oracle was sharpest: `/review` converged per phase, the drift gate reconciled
each phase against its Success Criteria, `/verify` certified branch completeness,
`/orient` rebuilt the system map. Re-running any of that here would be spend without
signal. The one audit that lives HERE by design is the test-intent recap half — cull,
coverage-net, and the weak-assertion sweep are all cross-phase questions.

What has _not_ happened is synthesis. You have seen five phases; you have not seen the
branch. This skill's whole job is to hand you that one artifact.

Output contract: ONE human-facing **recap**, plus a machine copy appended to
`~/.claude/branch-recap-receipts.jsonl`. It never runs `git add` on semantic files,
never commits, never opens a PR.

## Step 1: Cross-phase test audit

Dispatch `test-intent-reviewer` (pinned; omit `model`) — **cull + coverage-net + weak
scope** (`scope: cull` in its contract). Bug-pinning is structurally severed by the
coder/test-writer split and its hooks; do not run that half here.

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
Net-removed coverage goes to the top of the read-first queue.

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

Receipt line: `test audit: <n> culled, <n> coverage-lost of <m> pre-existing tests searched, <n> weak | coverage-net N/A — base suite empty | clean | skipped — no test files`.

Log the firing to the review flywheel (non-blocking; on failure mention and continue; skip if the audit was skipped):

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" \
  repo="$(basename "$(git rev-parse --show-toplevel)")" lane=branch-recap \
  test_intent_ran=1 test_intent=<n findings> culled=<n> coverage_lost=<n> weak=<n> \
  base_suite=<m pre-existing tests searched; 0 means the coverage-net gate did not run> \
  requires_mutation=<n> mutation_equivalent=<n of those the tester ruled EQUIVALENT> \
  mutation_open=<n still INDETERMINATE or unrouted> \
  result=<clean|findings>
```

Then emit the per-gate and per-finding rows per
`~/.claude/skills/_shared/finding-log.md` (read it) with
`gate=test-intent-reviewer lane=branch-recap scope=branch-exit`. A zero-finding
audit still logs its `kind=run` row.

## Step 2: Residue triage — `/stage`

Phases stage as they go (`/code` block B invokes `/stage` at each sign-off), so by now the
only unstaged work is what the closing phases themselves produced — the `/refactor` sweep's
diff, and anything `/fix` touched in step 1.

Skill-invoke `/stage`. Its SAFE tier is staged; its ESCALATE / READ / SKIM queue is the
residue you still owe a read. Do not reclassify or promote its tiers — `stage.mjs` is the
single source of truth, and only its deterministic SAFE tier is ever staged unread.

Nothing unstaged → receipt line `residue: none — all phases staged clean`.

**A classifier that could not answer did not return a clean tree.** The tiering reads the
diff of each unstaged path; where there is no diff to read — an all-new file, a greenfield
branch — it has nothing to classify, and its silence is byte-identical to a genuinely clean
tree. Check `git status --porcelain` yourself before writing the line: untracked or unstaged
paths that `/stage` returned no tier for go in the receipt as
`residue: <n> unclassified — no diff to tier, read them all`, and into **Still unstaged**
by name. Same rule as the denominator in step 1: a check that cannot fail has not passed.

## Step 3: Deferred-findings queue

The correctness loop gets one round per phase; a re-review's findings are
deferred to here rather than fixed in place. This is where that debt comes due —
if this step does not run, deferral was deletion.

```bash
jq -c --arg b "$(git branch --show-current)" \
  'select(.kind=="finding" and .actioned=="deferred" and .branch==$b)' \
  "${REVIEW_FINDINGS_FILE:-$HOME/.claude/review-findings.jsonl}"
```

Read the whole queue against the **branch** diff, not the phase each finding
came from — that wider bound is the reason deferral is worth anything, and some
findings die there because a later phase already resolved them.

Triage each into: **fix now** (route through `/fix`), **stale** (a later phase
resolved it — say which), or **carry** (real, out of scope for this branch —
route to `/escape` so it is not lost when this queue is filtered by branch).
Empty queue → receipt line `deferred: none`. Otherwise
`deferred: <n> fixed, <n> stale, <n> carried of <m>`.

A deferred `blocker` in this queue is a bug in the loop, not a work item: the
one-round budget exempts `blocker` findings from deferral. Say so explicitly if
one appears. A deferred `fix_induced=bug` is the same class — the loop diagnosed a
regression it created and then failed to fix it. Escalate it as a loop bug, not a
work item.

## Step 4: The recap

Assemble from what this session already holds — the per-phase walkthroughs, the review-loop
packets, the `/verify` packet, the `/orient` map. **Never dispatch an agent to reconstruct
prose.** Absent a handoff (fresh session), derive the change map from
`git diff --stat <base>...HEAD` and mark it `derived from diff — no handoff in context`.

```
## Branch recap — <repo> @ <branch>

Spec: <task-dir>

<one paragraph: what this branch does, from the spec>

### Change map (across phases)
- <path> — <one-line change intent>   [phase <n>]

### Cross-phase test audit
- <culled / COVERAGE-LOST / WEAK findings, or "clean">
- <denominator, always: "N of M pre-existing tests searched" or "coverage-net N/A — base suite had 0 tests, this gate did not run">
- <any REQUIRES-MUTATION items with their KILLED/SURVIVED/EQUIVALENT/INDETERMINATE verdicts, or marked unrouted-and-open>

### Deferred findings             (one-round budget, read at branch bound)
- <fixed / stale / carried, one line each, with the gate and disposition each came from; or "none">

### Smoke-test checklist          (from the /verify closing phase)
- <every human-only item, with steps>

### Open items                    (ask[], nit[], escapes — verbatim)

### Still unstaged                (from /stage, blast-radius order)
- <path> — <classifier reason>

Next: read the residue → run the smoke checklist → /adr → stage → /commit → open the PR.
```

Persist (non-blocking; on failure mention and continue):

```bash
printf '{"ts":"%s","repo":"%s","branch":"%s","test_audit":"%s","residue":%d,"files":%d}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$(git rev-parse --show-toplevel)")" \
  "$(git rev-parse --abbrev-ref HEAD)" "<clean|n culled|n coverage-lost>" \
  <unstaged count> <changed-file count> >> "$HOME/.claude/branch-recap-receipts.jsonl"
```

## What NOT to do

- **Never re-run a gate** — no second correctness pass, no re-verify, no re-orient. Reason at
  the top of this file. Re-running one hides the debt this skill exists to surface.
- **Never `git add` a semantic file, never commit, never open a PR** — output contract above.
- **Never edit code** — anything step 1 finds routes through `/fix`.
- **Never run `/adr`** — it is the user's own step, sequenced after the recap and before the
  PR opens so the record ships in the same PR. The recap's Next line points to it.

## Arguments

$ARGUMENTS
