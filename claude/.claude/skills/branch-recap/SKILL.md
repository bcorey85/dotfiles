---
name: branch-recap
description: The final closing phase — assemble a gated branch into one pre-PR handoff sheet. Reads only the branch's own process residue (the phase walkthroughs, the verify and test-audit receipts, git status) — never re-reads the codebase, never gates. Triages closing-phase residue and deferred findings, emits a recap receipt. Use for "recap", "branch recap", "wrap up the branch", "/branch-recap". Hands back a read queue — the staging and the commit stay the user's.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Branch recap

The fourth and last closing phase, and the exit-side counterpart to `/eng-spec`.

**No gates run here.** Every gate already fired at its sharpest oracle: per-phase `/review` convergence, drift-gate reconciliation, `/verify` completeness, `/test-audit` test gate.

**Not `/orient`.** `/orient` reads the **codebase** (how the change fits); this reads only the **branch's process residue** (walkthroughs, packets, receipts, `git status`) — "what remains before the PR?" Never re-reads code for a system map; consumes a prior `/orient` map or points the user to run one.

Output: ONE human **recap** + a machine row in `branch-recap-receipts.jsonl`. Never `git add` semantic files, commit, or open a PR.

## Step 1: Residue triage — `/stage`

Phases stage as they go, so the only unstaged work is what the closing phases produced (`/refactor` diff, `/fix` or `test-writer` touches in `/test-audit`).

Skill-invoke `/stage`: SAFE staged; ESCALATE/READ/SKIM queue is the residue you owe a read. Never reclassify tiers. On queue-stepping, `nvim-jump` each entry (`~/.claude/skills/_shared/nvim-jump.md`).

Nothing unstaged → receipt line `residue: none — all phases staged clean`.

**An unanswering classifier is not a clean tree.** All-new files / greenfield branches have no diff to tier — silence is byte-identical to clean. Check `git status --porcelain` yourself: untiered paths go in the receipt as `residue: <n> unclassified — read them all` and into **Still unstaged** by name.

## Step 2: Deferred-findings queue

One-round-per-phase residue comes due here — skip this step and deferral was deletion.

```bash
jq -c --arg b "$(git branch --show-current)" \
  'select(.kind=="finding" and .actioned=="deferred" and .branch==$b)' \
  "${REVIEW_FINDINGS_FILE:-$HOME/.claude/review-findings.jsonl}"
```

Read the queue against the **branch** diff — some findings died when a later phase resolved them.

Triage: **fix now** (`/fix`), **stale** (later phase resolved — say which), **carry** (real but out-of-scope — `/escape` so branch-filtering doesn't lose it). Empty → `deferred: none`, else `deferred: <n> fixed, <n> stale, <n> carried of <m>`.

A deferred `blocker` (or `fix_induced=bug`) is a loop bug, not a work item — escalate as such.

## Step 3: The recap

Assemble from session holdings (walkthroughs, packets, receipts, `git status`). **Never dispatch an agent for prose, never re-read code for a system map** (`/orient`'s job). No handoff (fresh session) → change map from `git diff --stat`, marked `derived from diff`.

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

- **Never re-run a gate** (no second correctness pass, re-verify, or test-gate re-run).
- **Never re-read code to situate** (no callers/siblings/LSP map — that's `/orient`; consume or say "not situated").
- **Never `git add` semantic files, commit, or open a PR.**
- **Never edit code** — fixes route through `/fix`.
- **Never run `/adr`** — the user's step after recap, before the PR, so the record ships in it.

## Arguments

$ARGUMENTS
