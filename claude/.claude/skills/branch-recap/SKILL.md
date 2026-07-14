---
name: branch-recap
disable-model-invocation: true
description: The final closing phase — reassemble a gated branch into one thing you can hold in your head before the PR. Cross-phase test audit, closing-phase residue triage, and a recap receipt. Use for "recap", "branch recap", "wrap up the branch", "/branch-recap". Never stages semantic changes and never commits — the user reads the queue and stages, then /commit.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Branch recap

The fourth and last closing phase, and the exit-side counterpart to `/eng-spec`.

**It is not a gate.** By the time you reach it every gate has already fired, and fired
where its oracle was sharpest: `/review` converged per phase, the drift gate reconciled
each phase against its Success Criteria, per-phase test-intent caught bug-pinning while
it was still phase-sized, `/verify` certified branch completeness, `/orient` rebuilt the
system map. Re-running any of that here would be spend without signal.

What has *not* happened is synthesis. You have seen five phases; you have not seen the
branch. This skill's whole job is to hand you that one artifact.

Output contract: ONE human-facing **recap**, plus a machine copy appended to
`~/.claude/branch-recap-receipts.jsonl`. It never runs `git add` on semantic files,
never commits, never opens a PR.

## Step 1: Cross-phase test audit

Dispatch `test-intent-reviewer` (pinned; omit `model`) — **cull + coverage-net scope only**.
Per-phase bug-pinning already ran in `/code`'s phase gate; do not re-run it here.

This half of the audit is inherently cross-phase and cannot be done phase-locally:

- **Test spam** — phase 2 and phase 4 each adding a test for the same behavior is
  invisible from inside either phase.
- **`COVERAGE-LOST`** — a test deleted in phase 1 and legitimately replaced in phase 3
  looks like lost coverage at phase 1, and only resolves when both are in view.

Hand it the branch diff (`git diff <base>...HEAD`) and the oracle (spec + acceptance
criteria). Findings route through `/fix`, then re-run the loop's execution gate.
Net-removed coverage goes to the top of the read-first queue.

Receipt line: `test audit: <n> culled, <n> coverage-lost | clean | skipped — no test files`.

## Step 2: Residue triage — `/stage`

Phases stage as they go (`/code` block B invokes `/stage` at each sign-off), so by now the
only unstaged work is what the closing phases themselves produced — the `/refactor` sweep's
diff, and anything `/fix` touched in step 1.

Skill-invoke `/stage`. Its SAFE tier is staged; its ESCALATE / READ / SKIM queue is the
residue you still owe a read. Do not reclassify or promote its tiers — `stage.mjs` is the
single source of truth, and only its deterministic SAFE tier is ever staged unread.

Nothing unstaged → receipt line `residue: none — all phases staged clean`.

## Step 3: The recap

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
- <culled / COVERAGE-LOST findings, or "clean">

### Smoke-test checklist          (from the /verify closing phase)
- <every human-only item, with steps>

### Open items                    (medium.ask, low[], escapes — verbatim)

### Still unstaged                (from /stage, blast-radius order)
- <path> — <classifier reason>

Next: read the residue → run the smoke checklist → stage → /commit.
After the PR opens: /adr.
```

Persist (non-blocking; on failure mention and continue):

```bash
printf '{"ts":"%s","repo":"%s","branch":"%s","test_audit":"%s","residue":%d,"files":%d}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$(git rev-parse --show-toplevel)")" \
  "$(git rev-parse --abbrev-ref HEAD)" "<clean|n culled|n coverage-lost>" \
  <unstaged count> <changed-file count> >> "$HOME/.claude/branch-recap-receipts.jsonl"
```

## What NOT to do

- **Never re-run a gate.** No second correctness pass, no re-verify, no re-orient. Each of
  those already fired at a boundary where its oracle was sharper than it would be here.
  Re-running them buys little, and their real function at this point is to shrink what you
  read — which is the debt this skill exists to surface, not hide.
- **Never `git add` a semantic file, never commit, never open a PR** — the residual read and
  the stage are the user's; `/commit` is its own skill.
- **Never edit code** — anything step 1 finds routes through `/fix`.
- **Never run `/adr`** — it is sequenced after the PR opens (it wants the PR link). The
  recap's Next line points to it.
- **Never re-run quality checks the execution gate already evidenced** — the 2-run cap in
  `~/.claude/CLAUDE.md` applies across the whole task.

## Arguments

$ARGUMENTS
