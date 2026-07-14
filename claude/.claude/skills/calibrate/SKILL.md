---
name: calibrate
description: Measure your reviewer's actual recall by seeding a known defect into the working diff, running the real reviewer blind, and checking whether it caught it. Answers the question the review metrics cannot - whether a zero-finding run means "clean" or "the instrument failed". Use for "calibrate the reviewer", "seed a defect", "is my review loop actually working", "/calibrate". Always restores the tree; never commits.
allowed-tools: [Agent, Bash, Read, Write, Edit, Glob, Grep]
---

# Calibrate

`review-metrics.jsonl` records what the reviewer FOUND. It cannot record what
the reviewer MISSED — so a 30% zero-finding rate is unreadable: it is either a
clean pipeline or a blind reviewer, and those look identical from the inside.
This skill supplies the missing denominator.

Method: seed one realistic defect into a real diff, dispatch the real reviewer
blind, record caught/missed. Ten runs gives a recall number. That number is the
prior on every future clean review.

**The tree is mutated.** Everything below exists to guarantee it is put back.

## Step 0: Preconditions

```bash
git rev-parse --show-toplevel && git status --porcelain
```

- Not a git repo → stop.
- **Lock file exists** (`~/.claude/calibration-lock.json`) → STOP. A previous
  run mutated a file and never restored it. Restore from the lock's
  `backup_path` first (step 5), then delete the lock. Never seed on top of an
  unrestored seed.
- Empty diff → stop: "nothing to calibrate; run this on a converged branch
  before you read it."

Run this on a CONVERGED diff — after the loop passed, before you read it. A
defect seeded into already-broken code measures nothing.

## Step 1: Pick the target

From `git diff --name-only`, choose ONE changed file with real logic (skip
docs, lockfiles, pure config). Prefer a file the loop passed clean — that is
exactly the population whose clean verdict you are testing.

## Step 2: Seed one defect

Read the file. Choose a defect class that is PLAUSIBLE for this code — the
mutation must look like something a coder agent would actually emit, not like
sabotage. A reviewer catching `x = null; x.foo()` proves nothing.

Defect classes (pick one; vary across runs, never repeat the same class twice
in a row — a reviewer can be good at one class and blind to another):

| Class            | Mutation                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------- |
| boundary         | `<` → `<=`, `i < n` → `i <= n`, off-by-one on a slice/index                              |
| inverted-guard   | drop a `!`, flip an early-return condition                                               |
| dropped-async    | remove an `await`, drop a `.catch`, fire-and-forget a promise                            |
| swapped-args     | transpose two same-typed params at a call site                                           |
| removed-check    | delete a null/undefined/empty guard that the code below relies on                        |
| wrong-error-path | swallow an error, return a default where it should throw                                 |
| stale-state      | read a value before the write that should precede it; drop a dependency from a hook/memo |
| resource-leak    | remove a cleanup/close/unsubscribe on one path                                           |

**Record before mutating**, then write the lock:

```bash
mkdir -p ~/.claude/calibration
cp <target> ~/.claude/calibration/$(basename <target>).bak
git diff -- <target> | sha256sum | cut -c1-16   # pre-mutation diff hash
```

```bash
jq -n --arg f "<target>" --arg b "$HOME/.claude/calibration/$(basename <target>).bak" \
      --arg h "<pre-mutation hash>" --arg c "<class>" --arg l "<line>" \
      '{ts: (now|todate), file: $f, backup_path: $b, pre_hash: $h, class: $c, line: $l}' \
  > ~/.claude/calibration-lock.json
```

The lock is the safety net: `calibration-guard.sh` (SessionStart) shouts if a
session ever starts with one present. Apply the mutation with **Edit** — one
line, minimal, no comment marking it.

## Step 3: Run the reviewer blind

Dispatch the SAME reviewer the loop's first iteration uses, so the number
transfers: `Agent`, `subagent_type: "code-reviewer"`, `model: "sonnet"`.

- Dispatch it as a normal review of the working diff. **Never mention
  calibration, seeding, or that a defect exists** — a primed reviewer is not
  the reviewer you run in production, and its recall number is worthless.
- `+deep` variant → dispatch `code-reviewer-deep` (pinned; omit `model`) and
  record `reviewer=deep`. Calibrate the tier you actually run.
- This is NOT `review-loop` — the loop would dispatch a coder and fix the seed,
  destroying the measurement (and putting an agent-authored fix in your tree).
  Never route calibration through the loop.

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
git diff -- <target> | sha256sum | cut -c1-16   # must equal pre_hash
```

- Matches → `rm ~/.claude/calibration-lock.json`.
- **Does not match** → STOP and tell the user, loudly, with the backup path and
  the target path. Do not delete the lock. Do not continue. A mismatch means
  their working tree is not what they think it is, and that outranks every
  other thing this skill does.

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

State the recall as a fraction with its N — `3/5 caught (sonnet)` — never as a
percentage until N ≥ 10. And say plainly what it licenses:

- **Recall is high** → your zero-finding runs are real. The loop is cheap
  insurance; trust it and read less.
- **Recall is low** → every clean review in `review-metrics.jsonl` is
  uninformative, and the 30% null rate is the instrument failing, not the code
  passing. The reviewer tier, not your reading, is what needs to change.

Below N=10, report the fraction and say it's provisional. Resist the urge to
conclude from three runs.

## What NOT to do

- **Never commit with a seed in the tree.** If `git commit` is even discussed
  while the lock exists, stop and restore first.
- **Never tell the reviewer it's a drill** — that measures a reviewer you don't
  have.
- **Never seed more than one defect per run.** Two seeds make caught/missed
  ambiguous and double the restore risk.
- **Never route through `review-loop`** — it fixes, which destroys the measurement.
- **Never seed into an acceptance-spec file or a migration.** If the restore
  ever fails there, the blast radius is real data.

## Arguments

$ARGUMENTS — `+deep` to calibrate the deep reviewer tier instead of sonnet.
