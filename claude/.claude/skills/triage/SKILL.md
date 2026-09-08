---
name: triage
description: Quick sizing pass on one incoming issue — pull the ticket (or take pasted info), bound the surface against the real repo, give an LoE bucket, and route it to /eng-spec, /code, or /debug. Use for "triage this", "how big is this", "does this need a spec", "size this ticket", "/triage". Read-only; produces no plan and no code.
allowed-tools:
  [
    Bash,
    Read,
    Glob,
    Grep,
    Agent,
    AskUserQuestion,
    Skill,
    mcp__jira__getJiraIssue,
    mcp__claude_ai_Atlassian__getJiraIssue,
  ]
---

# Triage — size it, then route it

One issue in, one routing verdict out — a **decision aid upstream of planning** (`/eng-spec` alone designs). Never designs, writes files, or touches code.

## Step 1: Get the issue

First match wins:

1. **Jira key/URL** in `$ARGUMENTS` or branch name → `Skill(pull-ticket)`. No MCP → continue on user text; none → stop.
2. **A `/pull-ticket` result already in the thread** → use it, don't re-fetch.
3. **Free text, a file path, a Slack/PR quote** → that is the issue. No ticket required.
4. **Nothing** → ask: "What am I sizing? Paste the ticket, link, or a description."

## Step 2: Bound the surface — HARD CAP

The estimate comes from knowing **which files change**, not from understanding how to change them.
Stop the moment you can name them.

- **≤8 read-only tool calls**, or **one** `Explore` dispatch (`model: "haiku"`) when the surface is
  genuinely unknown. Not both, never a second Explore.
- Grep entry points + nearest shipped analogue (that IS the estimate). Excerpts, not whole files.
- Hit the cap without a clear surface → that IS the finding: confidence `low`, and the unknown
  goes in the output.
- Do not run tests, do not reproduce the bug, do not read the whole module.

## Step 3: Size it

| Bucket | Shape | Default route |
| --- | --- | --- |
| **XS** | One value, string, flag, or line. Files already named. | `/code +fast` |
| **S** | One file or one layer. No new interface. | `/code` |
| **M** | Several files, interfaces already exist, approach is obvious. | `/code` (`+deep` if intertwined) |
| **L** | Crosses layers, or a new data/API shape, or an unresolved design fork. | `/eng-spec` + depth (below) |
| **XL** | Migration, or the ask is really several features wearing one ticket. | Split first, then `/eng-spec` + depth per piece |
| **?** | Bug whose root cause is unknown. | `/debug` first, re-triage after |

**Buckets are surface + uncertainty, not hours.** Hours only if asked — as a range naming what blows it.

### Overrides — these beat the table

- **Force `/eng-spec`**: unresolved design fork; auth/tenancy/money/migration in surface; untestable-as-written AC.
- **Force `/debug`** on symptom-without-cause. An unestimated bug is unestimatable — say so.
- **Never upgrade on size alone**: a mechanical sweep across 40 files (rename, config, codemod) is still `/code`. Volume is not design.
- **Never downgrade on a confident-sounding ticket**: weigh the surface you found, not the prose.

### Depth — `/eng-spec` routes only, appended to the route

- **STANDARD**: single-layer OR ≤3 phases, no migration/endpoint/dependency the
  ticket did not imply, nothing destructive (reclaim/expire/evict/revoke/invalidate).
- **DEEP**: anything else; migration, new endpoint/dependency, destructive action,
  or auth-boundary surface forces DEEP.
- Triage never emits GO-LEAN (trivial surface routes `/code`; leanness is
  `/eng-spec` Phase 3's call).

## Step 4: Report — this exact shape, nothing added

```
<KEY or slug> — <one-line restatement of the actual ask>
LoE: <XS|S|M|L|XL|?> · confidence <high|med|low>
Surface: <n> files — <path>, <path><, +n more>
Forks: <the design decision(s) someone must make, or "none">
Moves the estimate: <the one unknown that would shift the bucket, or "none">
→ <route>[ <depth>] — <why, ≤8 words>   (depth on `/eng-spec` routes only)
```

No preamble, no research dump. Underspecified past bounding → that IS the report: which answer unblocks, who owns it.

## Step 5: Hand off

Offer via `AskUserQuestion`: recommended first, adjacent second, `just the estimate` always. Choice → invoke with key/text plus the depth on `/eng-spec` routes; estimate-only → stop.

When the routing is L/XL and **no ticket exists**, add one line offering `/create-ticket` before the
spec.

## Arguments

$ARGUMENTS
