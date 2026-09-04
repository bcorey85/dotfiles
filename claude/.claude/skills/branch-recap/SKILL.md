---
name: branch-recap
description: The final closing phase — assemble a gated branch into one pre-PR handoff sheet. Reads only the branch's own process residue (the phase walkthroughs, the verify and test-audit receipts, git status) — never re-reads the codebase, never gates. Triages closing-phase residue and deferred findings, emits a recap receipt. Use for "recap", "branch recap", "wrap up the branch", "/branch-recap". Hands back a read queue — the staging and the commit stay the user's.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Branch recap

The fourth and last closing phase, and the exit-side counterpart to `/eng-spec`.

**It runs no gates.** By the time you reach it every gate has already fired, and fired
where its oracle was sharpest: `/review` converged per phase, the drift gate reconciled
each phase against its Success Criteria, `/verify` certified branch completeness, and
`/test-audit` ran the cross-phase test gate. Re-running any of that here would be spend
without signal.

What has _not_ happened is synthesis. You have seen the phases; you have not seen the
branch. This skill's whole job is to hand you that one artifact.

**This is not `/orient`.** The line between them is what each one reads. `/orient` reads
the **codebase** — callers, callees, siblings of the changed symbols — to answer "how does
this fit the code that did not change?"; run it any time, any scope. This skill reads only
the **branch's own process residue** — the per-phase walkthroughs, the review-loop packets,
the `/verify` and `/test-audit` receipts, `git status` — to answer "what do I still need to
read and do before I open the PR?" It never re-reads the codebase to build a system map. If
the recap needs that map, it consumes one a prior `/orient` produced this session, or the
Next line points the user to run `/orient` — it does not do that analysis itself.

Output contract: ONE human-facing **recap**, plus a machine copy appended to
`~/.claude/branch-recap-receipts.jsonl`. It never runs `git add` on semantic files,
never commits, never opens a PR.

## Step 1: Residue triage — `/stage`

Phases stage as they go (`/code` block B invokes `/stage` at each sign-off), so by now the
only unstaged work is what the closing phases themselves produced — the `/refactor` sweep's
diff, and anything `/fix` or a `test-writer` re-dispatch touched in the `/test-audit` phase.

Skill-invoke `/stage`. Its SAFE tier is staged; its ESCALATE / READ / SKIM queue is the
residue you still owe a read. Do not reclassify or promote its tiers — `stage.mjs` is the
single source of truth, and only its deterministic SAFE tier is ever staged unread. When
the user steps the queue, `nvim-jump` each entry per `~/.claude/skills/_shared/nvim-jump.md`.

Nothing unstaged → receipt line `residue: none — all phases staged clean`.

**A classifier that could not answer did not return a clean tree.** The tiering reads the
diff of each unstaged path; where there is no diff to read — an all-new file, a greenfield
branch — it has nothing to classify, and its silence is byte-identical to a genuinely clean
tree. Check `git status --porcelain` yourself before writing the line: untracked or unstaged
paths that `/stage` returned no tier for go in the receipt as
`residue: <n> unclassified — no diff to tier, read them all`, and into **Still unstaged**
by name. Same rule as the `/test-audit` denominator: a check that cannot fail has not passed.

## Step 2: Deferred-findings queue

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

## Step 3: The recap

Assemble from what this session already holds — the per-phase walkthroughs, the review-loop
packets, the `/verify` packet, the `/test-audit` receipt, `git status`.
**Never dispatch an agent to reconstruct prose, and never re-read the codebase to build a
system map — that is `/orient`'s job, not this one.** Absent a handoff (fresh session),
derive the change map from `git diff --stat <base>...HEAD` and mark it
`derived from diff — no handoff in context`.

```
## Branch recap — <repo> @ <branch>

Spec: <task-dir>

<one paragraph: what this branch does, from the spec>

### Change map (across phases)
- <path> — <one-line change intent>   [phase <n>]

### System map                    (only if an /orient ran this session — else this line: "not situated — run /orient for the system map")
- <the map that /orient produced, consumed verbatim; never rebuilt here>

### Cross-phase test audit         (from the /test-audit phase receipt)
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

- **Never re-run a gate** — no second correctness pass, no re-verify, no re-run of the
  `/test-audit` test gate. Reason at the top of this file. Re-running one hides the debt
  this skill exists to surface.
- **Never re-read the codebase to situate** — no callers/callees/siblings sweep, no LSP
  reference walk to build a system map. That is `/orient`. This skill consumes an orient map
  if one exists and otherwise says "not situated"; it never produces one.
- **Never `git add` a semantic file, never commit, never open a PR** — output contract above.
- **Never edit code** — deferred findings that need a fix route through `/fix`; this skill
  only triages and synthesises.
- **Never run `/adr`** — it is the user's own step, sequenced after the recap and before the
  PR opens so the record ships in the same PR. The recap's Next line points to it.

## Arguments

$ARGUMENTS
