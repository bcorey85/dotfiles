---
name: calibrate
description: Measure your reviewer's actual recall by seeding a known defect into the working diff, running the real reviewer blind, and checking whether it caught it. Answers the question the review metrics cannot - whether a zero-finding run means "clean" or "the instrument failed". Use for "calibrate the reviewer", "seed a defect", "is my review loop actually working", "/calibrate". Always restores the tree; never commits.
allowed-tools: [Agent, Bash, Read, Write, Edit, Glob, Grep]
---

# Calibrate

Metrics record what the reviewer FOUND, never what it MISSED — a 30% zero-finding rate is unreadable without the denominator this skill supplies.

Seed one realistic defect, dispatch the reviewer blind, record caught/missed. Ten runs = a recall number: the prior on every future clean review.

**The tree is mutated.** Everything below exists to guarantee it is put back.

## Step 0: Preconditions

```bash
git rev-parse --show-toplevel && git status --porcelain
```

- Not a git repo → stop.
- **Lock file exists** (`~/.claude/calibration-lock.json`) → STOP. A previous
  run mutated and never restored. Restore from `backup_path` first (step 5), then delete the lock — a gate blocking deletion means report-and-stop, never another mechanism. Never seed over an unrestored seed; the lock is shared with `mutation-tester` (by `.kind`) on purpose.
- Empty diff → stop: "nothing to calibrate; run this on a converged branch
  before you read it."

Run on a CONVERGED diff — post-loop, pre-read. Seeding into broken code measures nothing.

## Step 1: Pick the target

From `git diff --name-only` AND untracked files, choose ONE changed file with real logic (skip docs, lockfiles, pure config). Prefer untracked files (no prior version to diff against — where reviewers most likely miss) and files the loop passed clean (the population under test).

## Step 2: Seed one defect

Read the file. Choose a PLAUSIBLE defect class — something a coder agent would actually emit, not sabotage.

Defect classes (pick one; vary across runs, never repeat the same class twice
in a row — a reviewer can be good at one class and blind to another):

| Class | Mutation |
| --- | --- |
| boundary | `<` → `<=`, `i < n` → `i <= n`, off-by-one on a slice/index |
| inverted-guard | drop a `!`, flip an early-return condition |
| dropped-async | remove an `await`, drop a `.catch`, fire-and-forget a promise |
| swapped-args | transpose two same-typed params at a call site |
| removed-check | delete a null/undefined/empty guard that the code below relies on |
| wrong-error-path | swallow an error, return a default where it should throw |
| stale-state | read a value before the write that should precede it; drop a dependency from a hook/memo |
| resource-leak | remove a cleanup/close/unsubscribe on one path |

**Record before mutating**, then write the lock:

```bash
mkdir -p ~/.claude/calibration
cp <target> ~/.claude/calibration/$(basename <target>).bak
sha256sum <target> | cut -c1-16   # pre-mutation hash of the FILE
```

Hash the file's CONTENT, never `git diff`: for an untracked file the diff is empty before AND after, so a diff hash "verifies" a file still carrying the seed.

```bash
jq -n --arg f "<target>" --arg b "$HOME/.claude/calibration/$(basename <target>).bak" \
      --arg h "<pre-mutation hash>" --arg c "<class>" --arg l "<line>" \
      '{ts: (now|todate), kind: "calibrate", file: $f, backup_path: $b,
        pre_hash: $h, class: $c, line: $l}' \
  > ~/.claude/calibration-lock.json
```

The lock is the safety net (`calibration-guard.sh` shouts on sessions starting with one present). Apply with **Edit** — one line, minimal, unmarked.

## Step 3: Run the reviewer blind

Dispatch the SAME reviewer the loop's first iteration uses, so the number
transfers: `Agent`, `subagent_type: "code-reviewer"`, `model: "sonnet"`.

- Dispatch it as a normal review of the working diff. **Never mention
  calibration, seeding, or that a defect exists**.
- `+deep` variant → dispatch `code-reviewer-deep` (pinned; omit `model`) and
  record `reviewer=deep`. Calibrate the tier you actually run.
- This is NOT `review-loop` — the loop would dispatch a coder and fix the seed,
  destroying the measurement. Never route calibration through the loop.

## Step 4: Score

- **caught** — the reviewer flagged the seeded line, or described the defect at
  that call site. A finding on the right line for the wrong reason counts as
  caught (it puts your eyes there), but note it.
- **missed** — no finding on that line.
- Count `other_findings` — everything it flagged that was NOT your seed. On a
  converged diff these are candidate false positives; they are the precision
  side of the same instrument.

## Step 5: Restore — non-negotiable, runs even if the reviewer errored

Restore the file from `backup_path` using **Write** (not `git checkout` — that
would destroy the real uncommitted work in that file alongside the seed).

Then VERIFY the tree is back, by hash, not by eyeball:

```bash
sha256sum <target> | cut -c1-16   # must equal pre_hash
```

- Matches → `rm ~/.claude/calibration-lock.json`. **Gate-blocked removal = done**: report the result, state the block, print the user command. Never retry by another mechanism.
- **Does not match** → STOP, loudly, with both paths. Keep the lock. A mismatched tree outranks everything else this skill does.

## Step 6: Log

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" \
  out="$HOME/.claude/review-calibration.jsonl" \
  repo="$(basename "$(git rev-parse --show-toplevel)")" \
  reviewer=<sonnet|deep> class=<defect class> file=<target> \
  result=<caught|missed> other_findings=<n>
```

## Step 7: Report

Three lines. The seed, the verdict, and the running recall:

```bash
jq -s 'group_by(.reviewer)[] | {reviewer: .[0].reviewer, n: length,
  caught: (map(select(.result=="caught")) | length)}' ~/.claude/review-calibration.jsonl
```

State recall as a fraction with N (`3/5 caught (sonnet)`) — never a percentage below N=10 (provisional). What it licenses: **high** → zero-finding runs are real, trust the loop and read less; **low** → every clean review is uninformative, change the reviewer tier, not your reading.

## What NOT to do

- **Never commit with a seed in the tree.** If `git commit` is even discussed
  while the lock exists, stop and restore first.
- **Never tell the reviewer it's a drill**.
- **Never seed more than one defect** — two seeds make caught/missed ambiguous and double restore risk.
- **Never seed into an acceptance-spec file or a migration.** If the restore
  ever fails there, the blast radius is real data.

## Arguments

$ARGUMENTS — `+deep` to calibrate the deep reviewer tier instead of sonnet.
