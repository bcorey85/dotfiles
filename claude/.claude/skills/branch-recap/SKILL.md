---
name: branch-recap
description: The final closing phase — assemble a gated branch into one pre-PR handoff sheet. Reads only the branch's own process residue (the phase walkthroughs, the verify and test-audit receipts, git status) — never re-reads the codebase, never gates. Triages closing-phase residue and deferred findings, emits a recap receipt. Use for "recap", "branch recap", "wrap up the branch", "/branch-recap". Hands back a read queue — the staging and the commit stay the user's.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Branch recap

The fourth and last closing phase, and the exit-side counterpart to `/eng-spec`.

**No gates run here.** Every gate already fired at its sharpest oracle: per-phase `/review` convergence, drift-gate reconciliation, `/test-audit` test gate, `/verify-branch` completeness.

**Not `/orient`.** `/orient` reads the **codebase** (how the change fits); this reads only the **branch's process residue** (walkthroughs, packets, receipts, `git status`) — "what remains before the PR?" Never re-reads code for a system map; consumes a prior `/orient` map or points the user to run one.

Output: ONE human **recap** + a machine row in `branch-recap-receipts.jsonl`. Never `git add` semantic files, commit, or open a PR.

## Step 1: Residue triage — `/stage`

Phases stage as they go, so the only unstaged work is what the closing phases produced (`/refactor` diff, `/fix` touches in `/test-audit`, `/fix` touches from the Verify pass).

Skill-invoke `/stage`: SAFE staged; ESCALATE/READ/SKIM queue is the residue you owe a read. Never reclassify tiers.

Nothing unstaged → receipt line `residue: none — all phases staged clean`.

**An unanswering classifier is not a clean tree.** All-new files / greenfield branches have no diff to tier — silence is byte-identical to clean. Check `git status --porcelain` yourself: untiered paths go in the receipt as `residue: <n> unclassified — read them all` and into **Still unstaged** by name.

## Step 2: Deferred-findings queue

Per-phase residue of the review round budget comes due here — skip this step and deferral was deletion.

```bash
~/.claude/scripts/tools/ledger_deferred.py
```

It runs `ledger yield --deferred`, which reads the current repo and branch from the cwd and prints a header line, then one row per deferred finding: `finding_id, ts, gate, class, disposition, blocker, fix_induced, line, actioned, gate_agent_run_id, session`. `actioned=1` means a later edit to the finding's file landed inside its gate run's window. While the ledger cache is behind, the script waits up to about 90 s for it to catch up. Do not retry it yourself.

When the queue goes unread, the script prints the recap line, and the recap uses it as printed, never `deferred: none`:
- no `ledger`: `deferred: not tracked (ledger not installed)`.
- exit 75, the cache still behind after the wait: `deferred: not read (<reason>)` and the command that brings the cache up to date.
- other ledger failure: `deferred: not read (<reason>)`.

Read the queue against the **branch** diff — some findings died when a later phase resolved them. A row with `actioned=1` is marked **likely stale**. For the rest, read the gate agent transcript locally — `~/.claude/projects/*/<session>/subagents/agent-<gate_agent_run_id>.jsonl` — and match the row to its finding by gate, class and line. The ledger keeps no description, so the transcript is where the finding's text lives.

Triage: **fix now** (`/fix`), **stale** (later phase resolved — say which), **carry** (real but out-of-scope — `/escape` so branch-filtering doesn't lose it). Header only → `deferred: none`, else `deferred: <n> fixed, <n> stale, <n> carried of <m>`.

A deferred `blocker` (or `fix_induced=bug`) is a loop bug, not a work item — escalate as such.

## Step 2b: Companion branches

A plan step in another repo leaves a branch there that nothing tracks once this PR merges. For each other repo the spec's phases or handover list name, run `gh pr list --repo <owner/name> --head <branch> --state all` on the branch the plan names. Tell a pushed branch from a never-pushed one with `git ls-remote --heads <remote-url> <branch>` (empty output: not pushed). A pushed branch with no PR goes first under **Companion branches** as `<repo>@<branch> — no PR`, and the recap's `Next:` line starts with opening that PR. A branch that is not pushed is listed as `<repo>@<branch> — not pushed`, and `Next:` never says to open a PR for it; it says to push it. No other repo named → `companions: none`.

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
- <culled / WEAK findings, or "clean"; "no receipt" when no /test-audit receipt is in context — never "clean" without one>
- <denominator, always: "N plan promises walked">
- <any REQUIRES-MUTATION items with their KILLED/SURVIVED/EQUIVALENT/INDETERMINATE verdicts, or marked unrouted-and-open>

### Deferred findings             (round budget, read at branch bound)
- <fixed / stale / carried, one line each, with the gate and disposition each came from; or "none"; or "not tracked (ledger not installed)"; or "not read (<reason>)" with the command that brings the cache up to date; or "not read (<reason>)">

### Companion branches            (Step 2b)
- <repo>@<branch> — <PR url, or "no PR", or "not pushed">; or "none"

### Smoke-test checklist          (from the /verify-branch closing phase)
- <every human-only item, with steps>

### Open items                    (ask[], nit[] lines not ending `applied`, escapes — verbatim)

### Still unstaged                (from /stage, blast-radius order)
- <path> — <classifier reason>

Next: read the residue → run the smoke checklist → /adr → stage → /commit → open the PR.
```

Persist (non-blocking; on failure mention and continue):

```bash
if "$HOME/.claude/scripts/telemetry/telemetry_enabled.sh" 2>/dev/null; then
  printf '{"ts":"%s","repo":"%s","branch":"%s","test_audit":"%s","residue":%d,"files":%d}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$(git rev-parse --show-toplevel)")" \
    "$(git rev-parse --abbrev-ref HEAD)" "<clean|n culled|n weak|no receipt>" \
    <unstaged count> <changed-file count> >> "$HOME/.claude/branch-recap-receipts.jsonl"
fi
```

## What NOT to do

- **Never re-run a gate** (no second correctness pass, re-verify, or test-gate re-run).
- **Never re-read code to situate** (no callers/siblings/LSP map — that's `/orient`; consume or say "not situated").
- **Never `git add` semantic files, commit, or open a PR.**
- **Never edit code** — fixes route through `/fix`.
- **Never run `/adr`** — the user's step after recap, before the PR, so the record ships in it.

## Arguments

$ARGUMENTS
