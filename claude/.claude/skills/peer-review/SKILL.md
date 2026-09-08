---
name: peer-review
description: Peer-review someone else's PR — orient first (intent, change map, risk surface), then a report-only tiered review (blocking / suggestions / nits), then an optional one-at-a-time walkthrough with discussion. Never edits code, never enters the fix loop.
allowed-tools:
  [
    Agent,
    Bash,
    Read,
    Write,
    Glob,
    Grep,
    LSP,
    Skill,
    AskUserQuestion,
    mcp__jira__getJiraIssue,
  ]
---

# Peer Review

Assist a human peer review of someone else's PR. Two hard differences from `/review`:

1. **Report-only.** NEVER dispatch `/fix`, never edit files, never run the convergence loop, never log to `review-metrics.jsonl` (that flywheel measures OUR loop).
2. **Orientation before judgment** — what changed and why, before any finding.

## Modifiers

- `+deep` — dispatch `code-reviewer-deep` instead of `code-reviewer` (omit `model`; its frontmatter pins Opus). For security-sensitive, concurrent, or architecturally complex PRs.
- `+comment` — after the walkthrough, draft GitHub review comments and post ONLY after the user approves the exact text. Without it, nothing ever leaves the terminal.
- `+ephemeral` — skip the vault save below.

## Persist orientation to vault (default — `+ephemeral` skips)

After step 3, save the orientation block to `<vault>/Orientations/<yyyy-mm-dd>-<repo>-pr<number>.md` (`$VAULT_DIR` else `~/vault`) + capture line via `~/.local/bin/note`. Same-day re-review overwrites. Findings are NOT saved — they belong to the PR thread.

## Instructions

### 1. Resolve the PR

Arg is a PR number, URL, or head branch. Resolve with `gh pr view <arg> --json number,title,body,author,baseRefName,headRefName,url,additions,deletions,changedFiles,statusCheckRollup,isDraft`. No arg → the current branch's PR; if none, ask the user which PR.

Fetch existing review activity (for dedup in step 4):

```bash
bash "$(dirname "$CLAUDE_SKILL_DIR")/pr-comments/fetch-pr-comments" <number>
```

Then fetch the Jira ticket per `~/.claude/skills/_shared/jira-ticket.md` (read it) — **optional-ticket caller**: key from head branch, then title, then body; no key/MCP → note "reviewing without ticket context" and continue. Keep acceptance criteria verbatim (drives 4b).

### 2. Materialize the head without touching the working tree

Never `gh pr checkout` in the main tree, never stash. Use an isolated worktree:

```bash
git fetch origin "pull/<number>/head"
git worktree add "${TMPDIR:-/tmp}/peer-review-<number>" FETCH_HEAD
```

All file reads during review happen in the worktree. Compute the diff with `git diff "origin/<baseRefName>"...FETCH_HEAD` (name-only first for the file list, full diff for review). Remove the worktree in step 7 even on early exit.

### 3. Orientation (no judgment yet)

Present, in this order:

- **Intent vs diff**: PR + ticket claim, one line — then whether the diff matches. Drift is an observation, not a finding.
- **Ticket**: key, status, acceptance criteria verbatim (or "no ticket context" + why). Already-Done ticket → say so (follow-up or mislink).
- **Change map**: files by purpose, one line each, in **reading order** (core → callers → tests/config). Note the 1–3 files where the real change lives.
- **Risk surface**: only what's present — migrations, auth/permissions, public API or contract changes, concurrency, deleted code/guards, dependency bumps, config defaults flipped.
- **State**: CI status, draft/ready, who has already reviewed and how many open threads.

Then proceed directly to the full review (step 4) — no gate, no prompt.

### 4. Dispatch the review

Dispatch `code-reviewer` (or `code-reviewer-deep` with `+deep`; otherwise `model: "sonnet"`) with:

- The worktree path as code root + exact changed-file list (never rediscover scope). >5 files → split on the largest natural boundary (`review-loop` Step 3 heuristic), parallel dispatch.
- PR description + ticket summary/AC when found, as intent context. (AC _reconciliation_ stays in 4b.)
- Existing review-thread locations from step 1, tagged: "already raised by another reviewer — do not re-report; note only if your disposition differs materially".
- Framing: "Report-only peer review of a colleague's PR. Label each finding `blocker`/`ask`/`fix`/`nit` with concrete failure scenarios; each `blocker` states its firing precondition (realistic inputs/state, else not blocking) and its reproduction (exact input, command, or sequence). No fixes follow." Do NOT include a category checklist — the agent defines its own calibration.

### 4b. Acceptance-criteria reconciliation (main agent, when a ticket was found)

While the reviewers run, reconcile each acceptance criterion against the full diff yourself (you hold the whole diff from orientation; per-reviewer scopes are partial). Per criterion, one verdict with evidence:

- **Met** — cite the file:line(s) that satisfy it
- **Partial** — what's covered, what's missing
- **Not addressed** — nothing in the diff touches it
- **Not statically verifiable** — needs a runtime check or author confirmation; say which

Unmet ≠ automatically blocking (may be a deliberate first slice) — but an AC the description _claims_ done and the diff doesn't deliver → surface prominently.

### 4c. Surprise audit (always, before presenting findings)

This pass answers a different question — **"does this code do something a description-trusting reviewer would not expect?"** Runs on every full review, unasked; part of the first pass.

Main-agent, over the held diff + findings (no new dispatch). The frame is description-vs-operation, not more category sweep:

- **Hidden runtime dependencies** — a feature that silently hinges on something the description never mentions (a browser tab being open, a specific caller, an external timer).
- **Silent / permanent failure modes** — paths where a transient error, a swallowed exception, or an ordering choice (e.g. state written _before_ a best-effort side effect) loses data or work with no retry and no signal.
- **Scope surprises** — a limit, cap, default, or deletion that's broader or narrower than the description implies.
- **"Technically conforms but sharper than implied"** — edges meeting AC on paper while behaving in ways the author likely didn't intend discovered.

**Verify every candidate against the worktree first** — read enclosing code, check for the assumed-absent guard/retry, confirm cap scope. Not optional.

Merge survivors into step 5's tiers tagged `(surprise-lens)` (Blocking ones state preconditions, as in step 4). Drop refuted candidates silently.

### 5. Present findings, tiered

**Never a markdown table for a finding** — terminals collapse wide tables. One finding = short heading + prose. Tables only where every cell is a few words.

```
## Peer Review — PR #<n>: <title>

### Acceptance criteria — <KEY> (when a ticket was found)
| Criterion | Verdict | Evidence |     <- short cells only

### 🔴 Blocking (`blocker`)

**1. `path/file.ext:409-427` — <≤10-word title>**
<1-3 sentences: what's wrong, the concrete failure it produces, and the precondition that makes it fire. Cite file:line inline.>

### 🟠 Questions (`ask`)

**2. `path/file.ext:146-159` — <title>**
<1-2 sentences of context, then the question the author has to answer, as a question.>

### 🟡 Suggestions (`fix`, non-blocking)

**3. `path/file.ext:88` — <title>** <one sentence.>

### ⚪ Nits (`nit`)

**4. `path/file.ext:12` — <title>** <one clause.>

### Already raised by others
| Author | File:Line | Overlaps finding # |
```

Suggestions/nits: one line each. No `Issue:`/`Failure scenario:` labels — the table in disguise; fold into prose.

Number continuously across tiers. Then **offer the next step via AskUserQuestion** (two options):

- **Walk through the findings** — one at a time, with discussion; proceed to step 6.
- **Done for now** — stop; the user acts on the findings as-is.

(`+comment` stays a re-invocation modifier, not a menu option.)

### 6. Walkthrough (on "walk through")

One finding per turn, tier order, blocking first. **Never batch.** Before each, jump the user's editor to its anchor (`~/.claude/skills/_shared/nvim-jump.md`; main-checkout path, not worktree). Replies are conversation, not menu selection.

Before presenting each: read enclosing function + callers in the worktree (LSP; `rg` fallback — no installed deps there) and check for an elsewhere-guard. Then finding + concrete failing input + verdict:

- **CONFIRMED** — the trace from input to wrong behavior, quoting lines.
- **REFUTED** — quote the guard/invariant that makes it impossible. Say it plainly.
- **PLAUSIBLE** — reachable but depends on state you can't verify statically; say what would settle it (a test to run, a question to ask the author).

End each by asking: continue, drop, or stop. Track done/dismissed/comment-wanted for step 7. Dismissed = dropped, not re-argued.

The user can also name numbers (`walk 1 3 5`) to walk a subset, or type `next` / `stop` at any point.

### 7. Wrap up

- `+comment`: draft one GitHub comment per comment-marked finding (never dismissed; constructive tone — describe, suggest, don't command; PLAUSIBLE as questions). Show full draft; post via `gh` only after explicit approval.
- Always: `git worktree remove "${TMPDIR:-/tmp}/peer-review-<number>" --force` and confirm removal.

## Arguments

$ARGUMENTS
