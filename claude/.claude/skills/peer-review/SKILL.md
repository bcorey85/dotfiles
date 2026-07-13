---
name: peer-review
description: Peer-review someone else's PR — orient first (intent, change map, risk surface), then a report-only tiered review (blocking / suggestions / nits) with per-finding drill-down. Never edits code, never enters the fix loop.
allowed-tools: [Agent, Bash, Read, Write, Glob, Grep, LSP, Skill, AskUserQuestion, mcp__jira__getJiraIssue]
---

# Peer Review

Assist a human peer review of someone else's PR. Two hard differences from `/review`:

1. **Report-only.** The deliverable is understanding + findings for the user to act on as a reviewer. NEVER dispatch `/fix`, never edit files, never run the iter/convergence loop, never log to `~/.claude/review-metrics.jsonl` (that flywheel measures OUR loop; peer findings would pollute it).
2. **Orientation before judgment.** The user reads the PR through this skill — present what changed and why before any finding is surfaced.

## Modifiers

- `+deep` — dispatch `code-reviewer-deep` instead of `code-reviewer` (omit `model`; its frontmatter pins Opus). For security-sensitive, concurrent, or architecturally complex PRs.
- `+comment` — after drill-down, draft GitHub review comments and post ONLY after the user approves the exact text. Without it, nothing ever leaves the terminal.
- `+ephemeral` — skip the vault save below.

## Persist orientation to vault (default — `+ephemeral` skips)

After the step-3 gate is answered, save the orientation block (intent vs diff, ticket, change map, risk surface, state) to `<vault>/Orientations/<yyyy-mm-dd>-<repo>-pr<number>.md` (vault root: `$VAULT_DIR` if set, else `~/vault`) and append a capture line via `~/.local/bin/note "peer-review orientation: <repo>#<number> — [[<note filename without .md>]]"` so the daily recap links it. Re-reviewing the same PR same day overwrites the note. Findings are NOT saved to the vault — they belong to the PR thread and drill-down.

## Instructions

### 1. Resolve the PR

Arg is a PR number, URL, or head branch. Resolve with `gh pr view <arg> --json number,title,body,author,baseRefName,headRefName,url,additions,deletions,changedFiles,statusCheckRollup,isDraft`. No arg → the current branch's PR; if none, ask the user which PR.

Fetch existing review activity (for dedup in step 4):

```bash
bash "$(dirname "$CLAUDE_SKILL_DIR")/pr-comments/fetch-pr-comments" <number>
```

Then fetch the Jira ticket per `~/.claude/skills/_shared/jira-ticket.md` (read it). This skill is an **optional-ticket caller**: resolve the key from the PR's head branch, then title, then body; no key or no Jira MCP → note "reviewing without ticket context" and continue. When found, keep the acceptance criteria verbatim — they drive step 4b and the AC section of the report.

### 2. Materialize the head without touching the working tree

Never `gh pr checkout` in the main tree, never stash. Use an isolated worktree:

```bash
git fetch origin "pull/<number>/head"
git worktree add "${TMPDIR:-/tmp}/peer-review-<number>" FETCH_HEAD
```

All file reads during review happen in the worktree. Compute the diff with `git diff "origin/<baseRefName>"...FETCH_HEAD` (name-only first for the file list, full diff for review). Remove the worktree in step 7 even on early exit.

### 3. Orientation (no judgment yet)

Present, in this order:

- **Intent vs diff**: what the PR description and Jira ticket claim, one line — then whether the diff actually matches that scope. Flag drift ("description says X, but the diff also touches Y") as an observation, not a finding.
- **Ticket**: key, status, and the acceptance criteria verbatim (or "no ticket context" and why). If the ticket status is already Done, say so — the PR may be follow-up work or the ticket may be mislinked.
- **Change map**: files grouped by purpose, one line each, in **suggested reading order** — core logic first, then callers, then tests/config/generated. Note the 1–3 files where the real change lives.
- **Risk surface**: only what's present — migrations, auth/permissions, public API or contract changes, concurrency, deleted code/guards, dependency bumps, config defaults flipped.
- **State**: CI status, draft/ready, who has already reviewed and how many open threads.

Then gate with **AskUserQuestion**: `Full review` / `Focus review on <area>` (user supplies focus) / `Orientation only — stop here`. Do not dispatch reviewers until answered.

### 4. Dispatch the review

Dispatch `code-reviewer` (or `code-reviewer-deep` with `+deep`; otherwise `model: "sonnet"`) with:

- The worktree path as the code root and the exact changed-file list (never let it rediscover scope). >5 files → split along the largest natural boundary, same heuristic as `/review` step 3, parallel dispatch.
- The PR description — plus the Jira ticket summary and acceptance criteria when found — as intent context. (AC *reconciliation* stays with the main agent in step 4b; reviewers just get the intent.)
- Existing review-thread locations from step 1, tagged: "already raised by another reviewer — do not re-report; note only if your severity assessment differs materially".
- Framing: "Report-only peer review of a colleague's PR. Severity-tiered findings with concrete failure scenarios. No fixes will be applied from this review." Do NOT include a category checklist — the agent defines its own calibration.

### 4b. Acceptance-criteria reconciliation (main agent, when a ticket was found)

While the reviewers run, reconcile each acceptance criterion against the full diff yourself (you hold the whole diff from orientation; per-reviewer scopes are partial). Per criterion, one verdict with evidence:

- **Met** — cite the file:line(s) that satisfy it
- **Partial** — what's covered, what's missing
- **Not addressed** — nothing in the diff touches it
- **Not statically verifiable** — needs a runtime check or author confirmation; say which

An unmet criterion is not automatically blocking — the PR may be a deliberate first slice. Present the verdict; let the user judge. But an AC the description *claims* is done and the diff doesn't deliver → surface prominently.

### 5. Present findings, tiered

```
## Peer Review — PR #<n>: <title>

### Acceptance criteria — <KEY> (when a ticket was found)
| Criterion | Verdict | Evidence |

### 🔴 Blocking (CRITICAL / HIGH)
| # | File:Line | Issue | Failure scenario |

### 🟡 Suggestions (MEDIUM)
| # | File:Line | Issue |

### ⚪ Nits (LOW / style)
| # | File:Line | Issue |

### Already raised by others
| Author | File:Line | Overlaps finding # |
```

Number findings continuously across tiers. Then **actively offer the next step via AskUserQuestion** — do not rely on the user remembering a typed command. Options, in this order:

- **Run surprise audit (Recommended)** — second pass on what the description doesn't prepare a reader for (step 5b). Recommend it by default: it reliably surfaces blockers the category pass misses.
- **Dig into a finding** — user names the number(s); proceed to step 6.
- **Done for now** — stop; the user acts on the findings as-is.

(`+comment` stays a re-invocation modifier, not a menu option.) If the user picks the audit, run step 5b; after it, offer the same menu again minus the audit. The user can always type `dig into <#>` or `surprise audit` directly instead of using the menu.

### 5b. Surprise audit (user accepts the offer, or types "surprise audit")

A category-tiered review answers "is this line a bug?". This pass answers a different question — **"does this code do something a reviewer who trusted the PR/ticket description would not expect?"** — and it reliably surfaces blockers the first pass misses. Run it only when the user asks; it's a deliberate second look, not part of the default report.

Main-agent, over the diff and findings you already hold (no new dispatch). The frame is the gap between what the description leads a reader to expect and what the code operationally does — not more of the same category sweep. Look for:

- **Hidden runtime dependencies** — a feature that silently hinges on something the description never mentions (a browser tab being open, a specific caller, an external timer).
- **Silent / permanent failure modes** — paths where a transient error, a swallowed exception, or an ordering choice (e.g. state written *before* a best-effort side effect) loses data or work with no retry and no signal.
- **Scope surprises** — a limit, cap, default, or deletion that's broader or narrower than the description implies.
- **"Technically conforms but sharper than the ticket implies"** — edges that meet the acceptance criteria on paper while behaving in a way the author likely didn't intend a reviewer to discover.

**Verify every candidate against the worktree before presenting it** — read the enclosing code, check for the scheduler/guard/retry the candidate assumes is absent, confirm the true scope of a cap or filter. This step is not optional: in the run this pass came from, verification scope-corrected one "blocker" candidate down to a non-issue. Presenting an unverified surprise as confirmed relays a false positive to a colleague, the exact failure this skill guards against.

Merge survivors into the existing tiers, tagged `(surprise-lens)` so the user sees they came from this pass, not the category review. Drop refuted candidates silently (or note one line if the user would otherwise expect it). Then re-present the step-5 menu minus the audit.

### 6. Drill-down (on "dig into N")

Main-agent, read-only, in the worktree: read the enclosing function and its callers (LSP find-references; `rg` fallback — the worktree has no installed deps, so the language server may not resolve), check whether the failure path is guarded elsewhere, and construct a concrete failing input. Verdict:

- **CONFIRMED** — evidence: the trace from input to wrong behavior, quoting lines.
- **REFUTED** — quote the guard/invariant that makes it impossible. Note it so the user doesn't relay a false positive to a colleague.
- **PLAUSIBLE** — reachable but depends on state you can't verify statically; say what to check (a test to run, a question to ask the author).

### 7. Wrap up

- `+comment` present: draft one GitHub comment per user-selected finding (constructive reviewer tone — describe the failure scenario, suggest, don't command; phrase PLAUSIBLE items as questions). Show the full draft and post via `gh` only after explicit approval.
- Always: `git worktree remove "${TMPDIR:-/tmp}/peer-review-<number>" --force` and confirm removal.

## Arguments

$ARGUMENTS
