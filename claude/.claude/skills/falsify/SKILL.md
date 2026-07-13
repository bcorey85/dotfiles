---
name: falsify
disable-model-invocation: true
description: Attack ONE claim you name. Dispatches parallel refuters to find the counterexample in the repo — the row, the code path, the state where your claim is false. Read-only, report-only. You invoke it; it is never a gate and never runs itself.
allowed-tools: [Bash, Read, Glob, Grep, LSP, Agent]
---

# Falsify

You are handed **one claim, named by the user.** Not a plan, not a decision log,
not a diff. One sentence they are about to bet on.

Your job is not to assess it, summarize it, weigh its risk, or produce a risk
matrix. **Find the counterexample.**

## What this is not

- **Not a gate.** Nothing blocks on it. Nothing auto-invokes it. If you are
  reading this file because some other skill dispatched you, that skill is wrong.
- **Not a survey.** Do not enumerate bug classes or consult a checklist. Your
  target comes only from what the user actually said.
- **Not a search of git history, PRs, or issues.** Read the **working tree**:
  code, schema, config, tests, comments. Never `git log`, never `gh`. The
  question is what the code does, not what someone once said about it.

## 1. Restate the claim as a falsifiable proposition

Say it back in one sentence, **including the implicit part** — which is usually
the part that is actually load-bearing. "Check whether the owner already has a
member record" implicitly asserts *"an owner's member record is uniquely
identified by (project, user)."* **That implicit sentence is the target.** Show
the user the sentence you are about to attack, so they can correct it if you
aimed at the wrong one.

## 2. Refute — in parallel

Dispatch refuters (omit `model`) with a concrete mandate: **find the row, the
code path, the state where this is false.** Not "assess the risk." Search every
write path, not the obvious one: creation, acceptance, fan-out, sync, backfill,
seeds, migrations, admin tooling, tests.

**If the claim is shaped like *"we know X because we looked at Y"*** — does this
record exist? is this the same user? is this process still alive? is this value
unique? — use this refuter verbatim, and add it to whatever else you dispatch:

> *The check you are about to write — list every situation already out there that
> could fool it. For each: would the check find it and wrongly conclude "already
> handled"? Or miss it, and create a duplicate?*

It names no column and hints at nothing. Keep it that way. Feeding a refuter a
hint is how you get back the answer you already had.

## 3. Report — two buckets, nothing else

- **REFUTED** — the counterexample, at `file:line`, with the concrete state that
  breaks the claim. Quote the code.
- **UNREFUTED** — you searched and found nothing that breaks it. Say exactly what
  you searched, so the user can judge the silence.

No preamble, no recommendations, no "consider also…". If nothing was refuted, say
so in one line. **A refuted claim is not a finding to file — it reopens the
decision that rested on it, and that is the user's call, not yours.**

## What this tool actually does, measured

Blind, on 13 sealed real-world tickets whose shipped bug was known: **4 refuted
the real mechanism. 3 of 9 on the check-shaped ones.** Read that number before
you trust an UNREFUTED.

**It finds the right class and usually the wrong instance.** In failure after
failure it named the correct decision and then attacked a neighbour — it named a
coupling and cleared it, found a *sibling* of the real bug, and once
**recommended the shipped bug as the design.**

**The four it caught share one property: the counterexample was already written
down.** A PID field written and never read. A comment claiming membership "was
already validated" on a path where it wasn't. A scheduler that silently
auto-disables at ten failures. **It wins when the contradiction is on disk and it
loses when the contradiction must be imagined** — a row that could exist, a
default that could change, a name that could collide.

So: point it at a claim the repo can contradict. **UNREFUTED means "not written
down anywhere I looked." It does not mean true.**
