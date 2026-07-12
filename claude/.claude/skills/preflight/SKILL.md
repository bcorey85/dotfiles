---
name: preflight
disable-model-invocation: true
description: Exit front door for the branch — one command between "the loop converged" and "you stage". Runs the pre-commit ladder in order: mechanical /stage triage (when installed) → lane-scoped /verify → orient (no-lane) → read-surface triage → receipt. Use for "preflight", "wrap up the branch", "ready to commit", "/preflight". Never stages semantic changes and never commits — the user reads the queue and stages, then /commit.
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

## Step 1: Mechanical triage — `/stage` (runs only when installed)

`test -f ~/.claude/skills/stage/SKILL.md`

**Present** → Skill-invoke `/stage` and record its summary for the receipt.
Interface contract: `/stage` is DETERMINISTIC — its classifier stages only
the SAFE tier (mechanical, invariant-verified) and returns the rest as a
reading queue ordered by blast radius. It dispatches no reviewers, produces
no findings, and never stages anything semantic. (The former Opus verify/
suppress tier was removed 2026-07-11 — a model verdict must never license
the human to skip reading semantic changes.)

**Absent** → one receipt line: `stage triage: skipped — /stage not
installed`; step 3's manual classification covers the gap.

Staging only moves the index, not content — it may run either side of verify.

## Step 1.5: Test-intent audit — only when test files changed

`git diff --name-only` hits a test file → dispatch `test-intent-reviewer`
(pinned; omit `model`), handing it the oracle (ticket / plan success criteria)
so it judges assertions against INTENDED behavior, not the implementation.

This is the one reviewer preflight still dispatches, and it survives because
it produces FINDINGS for you, not permission to skip reading: a test that pins
a bug is invisible to a correctness reviewer (the code and the test agree) and
invisible to the execution gate (it passes). It never stages anything.

- `weak/bug-pinning` verdicts → route through `/fix`, then re-run the loop's
  execution gate.
- Net-removed coverage → it reports where the assertion went, or
  `COVERAGE-LOST`. Put that file at the top of the read-first queue.
- Receipt line: `test-intent: <n> flagged | clean | skipped — no test files`.

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

## Step 2.5: Orient — no-lane branches only

On a lane branch (resolve exit 0 or 5), skip: the plan's Orient closing phase
owns it, and running it here doubles the spend. On exit 4 (no lane) —
Skill-invoke `/orient`: no closing phase exists on this path, so this is the
only place the mental map gets rebuilt before the user reads the diff. Receipt
line either way: `orient: ran — <vault note link>` or
`orient: skipped — lane closing phase owns it`.

`/finalize` is NOT run here — it is sequenced after the PR opens (live mode
wants the PR link). The receipt's Next section points to it on the deep-plan
lane.

## Step 3: Read-surface triage (report-only)

When `/stage` ran, its SAFE-staged/queue split IS the triage — render the
queue in its blast-radius order. Otherwise classify every changed file,
conservatively:

- **stage-ready** — reviewed, low blast radius, no open ask item: docs and
  `*.md`, lockfiles/generated files, formatting-only hunks, test-only files
  the loop passed.
- **read-first** — everything else, and always: enforcement/config surfaces
  (CI, hooks, lint/gate config), exported contracts and public API, migrations
  and auth/payment paths, anything the loop flagged `load_bearing_clean`, any
  file carrying an open ask item, anything you can't confidently classify.

Emit the exact `git add -- <stage-ready files>` command for the user. NEVER
run it — staging is the human touchpoint; only `/stage`'s deterministic SAFE
tier is ever staged unread, and only by that script.

## Step 4: The receipt

Assemble from what this session already knows — degrade gracefully, never
dispatch an agent to reconstruct prose. Sources, best-first: the review-loop
packet (status, `fixed[]`, `medium.ask`, `test_intent.ask`, `low[]`,
`load_bearing_clean`), the handoff block (files + change intents,
`tests-run`), `/tmp/review-gate.log`, the `/verify` packet, the `/stage`
triage (staged count + queue). Absent handoff (fresh session) → derive the file list from git and
mark it `derived from diff — no handoff in context`.

```
## Preflight receipt — <repo> @ <branch>

Lane: deep-plan <ticket> | eng-spec <file> | none (completeness not certified)

| Stage          | Result                                                    |
| -------------- | --------------------------------------------------------- |
| review loop    | converged iter <N>, fixed <n> | no packet in context      |
| execution gate | <cmd> → exit 0 | not evidenced                            |
| stage triage   | <n> SAFE staged, queue <m> | skipped — <reason>           |
| test-intent    | <n> flagged | clean | skipped — no test files            |
| verify         | clean | gaps → routed | skipped — no lane                 |
| orient         | ran → <vault note> | skipped — lane owns it               |

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
printf '{"ts":"%s","repo":"%s","branch":"%s","lane":"%s","review":"%s","stage_triage":"%s","test_intent":"%s","orient":"%s","verify":"%s","files":%d,"read_first":%d}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$(git rev-parse --show-toplevel)")" \
  "$(git rev-parse --abbrev-ref HEAD)" "<lane>" "<review result>" "<triage result>" \
  "<test-intent result>" "<ran|skipped>" "<verify result>" \
  <changed-file count> <read-first count> >> "$HOME/.claude/preflight-receipts.jsonl"
```

## What NOT to do

- **Never `git add`, never commit, never open a PR** — the residual read and
  the stage are the user's; `/commit` is its own skill.
- **Never re-review a converged diff** — no second correctness pass, here or
  anywhere. A converged loop already reviewed it; a second reviewer over the
  same diff buys little (reviewer-agent precision is low) and its real function
  is to shrink what you read, which is the debt this ladder exists to surface.
  `test-intent-reviewer` (step 1.5) is the sole exception: it audits test
  INTENT against the oracle, which no other gate can see.
- **Never edit code** — anything found routes through `/fix`.
- **Never run `/finalize` pre-PR**, and never run `/orient` on a LANE branch —
  the plan's Orient closing phase owns it there; doubling it doubles the
  spend. (No-lane branches DO run it — step 2.5 is the only orient those
  branches get.)
- **Never re-run quality checks the execution gate already evidenced** — the
  2-run cap in `~/.claude/CLAUDE.md` applies across the whole task.

## Arguments

$ARGUMENTS
