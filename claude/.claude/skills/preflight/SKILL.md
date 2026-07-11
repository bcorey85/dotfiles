---
name: preflight
description: Exit front door for the branch — one command between "the loop converged" and "you stage". Runs the pre-commit ladder in order: /stage deep scan (when installed) → lane-scoped /verify → read-surface triage → receipt. Use for "preflight", "wrap up the branch", "ready to commit", "/preflight". Never stages and never commits — the user stages, then /commit.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Preflight

The exit-side front door, symmetric to `/plan` on the entry side. It exists so
the pre-commit ladder runs by POLICY, not memory: every stage below either
fires or is reported in the receipt as skipped-with-reason. A stage silently
not-run is the failure mode this skill deletes.

Output contract: ONE human-facing artifact — the **receipt** — that the user
reads INSTEAD of the raw diff, plus a machine copy appended to
`~/.claude/preflight-receipts.jsonl`. Preflight never runs `git add`, never
commits, never opens a PR.

## Step 0: Preconditions

- `git status --porcelain` empty → stop: "nothing in flight".
- If the tree's last write came from a coder dispatch with no reviewer pass
  after it, dispatch the review loop first (`/review`) — preflight assumes a
  CONVERGED diff and never substitutes for the loop. (`review-commit-gate`
  would block the eventual commit anyway; catch it here, not there.)

## Step 1: Deep scan — `/stage` (runs only when installed)

`test -f ~/.claude/skills/stage/SKILL.md`

**Present** → Skill-invoke `/stage` and record its summary for the receipt.
Interface contract the imported version must satisfy (adapt `/stage` on
import, not this file):

- Scans the converged diff with `code-reviewer-deep` + the test-intent agent
  (both Opus-pinned; omit `model`). This is the escalation tier above the
  loop's Sonnet passes — the ONLY place a second full review runs.
- Findings route through `review-loop` (`mode: fix-first`, `caller: fix`,
  handoff block per `~/.claude/skills/_shared/handoff-block.md`) — never
  fixed ad hoc outside the loop's gate tracking.
- Every catch logs one `log-review-metrics` line with `source=stage` — the
  marginal-catch rate over the converged Sonnet loop is the number that
  decides whether this tier keeps its Opus bill, and it must be visible to
  `/audit review`.
- Prestages hunks it judges safe; returns `{catches, prestaged[], residual[]}`.

**Absent** → one receipt line: `stage scan: skipped — /stage not installed`.
Do NOT improvise the pass with your own `code-reviewer-deep` dispatch; the
escalation tier is `/stage`'s job and runs only through it.

Ordering note: the scan (and any fixes/test culls it triggers) runs BEFORE
verify, so verify certifies the diff that will actually ship. Prestaging only
moves the index, not content — it may happen either side of verify.

## Step 2: Completeness — `/verify` (lane-scoped)

```bash
bash ~/.claude/scripts/resolve-task-dir.sh "$ARGUMENTS"
```

- Exit 0 (deep-plan) or 5 (eng-spec) → Skill-invoke `/verify`, passing the
  resolved path. Gaps found → `/verify` owns the escape logging and `/fix`
  routing; follow it to clean before continuing.
- Exit 4 → skip; receipt line: `verify: skipped — no plan lane (completeness
  not certified)`. Do not run a degraded verify against nothing.
- Exit 3 → AskUserQuestion: which match.

`/finalize` is NOT run here — it is sequenced after the PR opens (live mode
wants the PR link). The receipt's Next section points to it on the deep-plan
lane.

## Step 3: Read-surface triage (report-only)

When `/stage` ran, its `prestaged[]`/`residual[]` split IS the triage — render
it. Otherwise classify every changed file, conservatively:

- **stage-ready** — reviewed, low blast radius, no open ask item: docs and
  `*.md`, lockfiles/generated files, formatting-only hunks, test-only files
  the loop passed.
- **read-first** — everything else, and always: enforcement/config surfaces
  (CI, hooks, lint/gate config), exported contracts and public API, migrations
  and auth/payment paths, anything the loop flagged `load_bearing_clean`, any
  file carrying an open ask item, anything you can't confidently classify.

Emit the exact `git add -- <stage-ready files>` command for the user. NEVER
run it — staging is the human touchpoint, until an installed `/stage` owns
the safe half.

## Step 4: The receipt

Assemble from what this session already knows — degrade gracefully, never
dispatch an agent to reconstruct prose. Sources, best-first: the review-loop
packet (status, `fixed[]`, `medium.ask`, `test_intent.ask`, `low[]`,
`load_bearing_clean`), the handoff block (files + change intents,
`tests-run`), `/tmp/review-gate.log`, the `/verify` packet, the `/stage`
summary. Absent handoff (fresh session) → derive the file list from git and
mark it `derived from diff — no handoff in context`.

```
## Preflight receipt — <repo> @ <branch>

Lane: deep-plan <ticket> | eng-spec <file> | none (completeness not certified)

| Stage          | Result                                                    |
| -------------- | --------------------------------------------------------- |
| review loop    | converged iter <N>, fixed <n> | no packet in context      |
| execution gate | <cmd> → exit 0 | not evidenced                            |
| stage scan     | <n> catches (logged source=stage) | skipped — <reason>    |
| verify         | clean | gaps → routed | skipped — no lane                 |

### Changes  (from handoff | derived from diff)
- <path> — <one-line change intent>

### Read first — your surface
- <file> — <why>

### Stage-ready (reviewed, low blast radius)
git add -- <files>

### Smoke-test checklist   (from the /verify packet, when a lane ran)
### Open items             (medium.ask, test_intent.ask, low — verbatim)

Next: read the read-first set → run the smoke checklist → stage → /commit.
Deep-plan lane: after the PR opens, /finalize.
```

Persist (non-blocking; on failure mention and continue):

```bash
printf '{"ts":"%s","repo":"%s","branch":"%s","lane":"%s","review":"%s","stage_scan":"%s","verify":"%s","files":%d,"read_first":%d}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$(git rev-parse --show-toplevel)")" \
  "$(git rev-parse --abbrev-ref HEAD)" "<lane>" "<review result>" "<scan result>" "<verify result>" \
  <changed-file count> <read-first count> >> "$HOME/.claude/preflight-receipts.jsonl"
```

## What NOT to do

- **Never `git add`, never commit, never open a PR** — the residual read and
  the stage are the user's; `/commit` is its own skill.
- **Never re-review a converged diff yourself** — no ad-hoc
  `code-reviewer-deep` dispatch; the escalation tier exists only via `/stage`.
- **Never edit code** — anything found routes through `/fix`.
- **Never run `/finalize` pre-PR**, and never run `/orient` here — Orient is
  its own closing phase; running it inside preflight doubles the spend.
- **Never re-run quality checks the execution gate already evidenced** — the
  2-run cap in `~/.claude/CLAUDE.md` applies across the whole task.

## Arguments

$ARGUMENTS
