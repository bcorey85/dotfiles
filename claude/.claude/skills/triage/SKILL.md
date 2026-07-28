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

One issue in, one routing verdict out. This is a **decision aid upstream of planning**, not a
planning lane: `/eng-spec` remains the only lane that designs anything. Triage never designs,
never writes files, never touches code.

## Step 1: Get the issue

First match wins:

1. **Jira key or URL** in `$ARGUMENTS`, or a key in the branch name → invoke `Skill(pull-ticket)`
   with it and use its result. Jira MCP unavailable → say so and continue on whatever text the
   user gave; if there is none, stop.
2. **A `/pull-ticket` result already in the thread** → use it, don't re-fetch.
3. **Free text, a file path, a Slack/PR quote** → that is the issue. No ticket required.
4. **Nothing** → ask: "What am I sizing? Paste the ticket, link, or a description."

## Step 2: Bound the surface — HARD CAP

The estimate comes from knowing **which files change**, not from understanding how to change them.
Stop the moment you can name them.

- **≤8 read-only tool calls**, or **one** `Explore` dispatch (`model: "haiku"`) when the surface is
  genuinely unknown. Not both, never a second Explore.
- Grep for the entry points and the nearest existing analogue — the closest thing already shipped is
  the estimate. Read excerpts, not whole files.
- Hit the cap without a clear surface → that IS the finding: confidence `low`, and the unknown
  goes in the output.
- Do not run tests, do not reproduce the bug, do not read the whole module.

## Step 3: Size it

| Bucket | Shape                                                                  | Default route                           |
| ------ | ---------------------------------------------------------------------- | --------------------------------------- |
| **XS** | One value, string, flag, or line. Files already named.                 | `/code +fast`                           |
| **S**  | One file or one layer. No new interface.                               | `/code`                                 |
| **M**  | Several files, interfaces already exist, approach is obvious.          | `/code` (`+deep` if intertwined)        |
| **L**  | Crosses layers, or a new data/API shape, or an unresolved design fork. | `/eng-spec`                             |
| **XL** | Migration, or the ask is really several features wearing one ticket.   | Split first, then `/eng-spec` per piece |
| **?**  | Bug whose root cause is unknown.                                       | `/debug` first, re-triage after         |

**Buckets are surface + uncertainty, not hours.** Never quote hours or days unless asked; if asked,
give a range and name what would blow it.

### Overrides — these beat the table

- **Force `/eng-spec` at any size**: an unresolved design fork (two plausible approaches with
  different blast radius); auth, tenant isolation, money, or a data migration in the surface;
  acceptance criteria that can't be made testable as written.
- **Force `/debug`**: the ticket describes a symptom and no one has named the cause. An unestimated
  bug is unestimatable — say so instead of guessing a bucket.
- **Never upgrade on size alone**: a mechanical sweep across 40 files (rename, config, codemod) is
  still `/code`. Volume is not design.
- **Never downgrade on a confident-sounding ticket**: a tight description hides work as often as it
  reflects it. Weigh the surface you found, not the prose.

## Step 4: Report — this exact shape, nothing added

```
<KEY or slug> — <one-line restatement of the actual ask>
LoE: <XS|S|M|L|XL|?> · confidence <high|med|low>
Surface: <n> files — <path>, <path><, +n more>
Forks: <the design decision(s) someone must make, or "none">
Moves the estimate: <the one unknown that would shift the bucket, or "none">
→ <route> — <why, ≤8 words>
```

No preamble, no research dump, no restating the ticket body. If the ticket is underspecified enough
that the surface can't be bounded, that is the report — say which answer unblocks it and who owns it.

## Step 5: Hand off

Offer the route through `AskUserQuestion`: the recommended route first, the adjacent one second
(`/eng-spec` ↔ `/code`), and `just the estimate, don't start` always available. On a choice, invoke
that skill with the ticket key or the issue text. On "just the estimate", stop.

When the routing is L/XL and **no ticket exists**, add one line offering `/create-ticket` before the
spec — an XL with no ticket usually needs splitting first.

## Arguments

$ARGUMENTS
