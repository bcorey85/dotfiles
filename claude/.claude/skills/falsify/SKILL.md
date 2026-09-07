---
name: falsify
disable-model-invocation: true
description: Attack ONE claim you name. Dispatches parallel refuters to find the counterexample in the repo — the row, the code path, the state where your claim is false. Read-only, report-only. You invoke it; it is never a gate and never runs itself.
allowed-tools: [Bash, Read, Glob, Grep, LSP, Agent]
---

# Falsify

You are handed **one claim, named by the user** — one sentence they are about to bet on. Not a plan, log, or diff.

Your job is not to assess it, summarize it, weigh its risk, or produce a risk
matrix. **Find the counterexample.**

## What this is not

- **Not a gate.** Nothing blocks or auto-invokes. Dispatched here by another skill means that skill is wrong.
- **Not a survey.** No bug-class enumeration, no checklists. Target comes only from what the user said.
- **Not a search of git history, PRs, or issues.** Read the **working tree**:
  code, schema, config, tests, comments. Never `git log`, never `gh`.

## 1. Restate the claim as a falsifiable proposition

Say it back in one sentence, **including the implicit part** (usually the load-bearing part — e.g. a membership check implicitly asserts uniqueness by (project, user)). Show it so the user can correct your aim.

## 2. Refute — in parallel

Dispatch refuters (omit `model`): **find the row, code path, state where this is false.** Every write path, not the obvious one.

**If the claim is shaped like _"we know X because we looked at Y"_** — does this
record exist? is this the same user? is this process still alive? is this value
unique? — use this refuter verbatim, and add it to whatever else you dispatch:

> _The check you are about to write — list every situation already out there that
> could fool it. For each: would the check find it and wrongly conclude "already
> handled"? Or miss it, and create a duplicate?_

It names no column and hints at nothing — keep it that way. Hinted refuters return your own answer.

## 3. Report — two buckets, nothing else

- **REFUTED** — the counterexample, at `file:line`, with the concrete state that
  breaks the claim. Quote the code.
- **UNREFUTED** — you searched and found nothing that breaks it. Say exactly what
  you searched, so the user can judge the silence.

No preamble, no recommendations. **A refuted claim reopens its decision — a user call, not a filing.**

## Scope

This wins only on contradictions already **on disk** (unread field, check-claiming comment, opposite default). Loses on imagined ones (could-exist rows, could-change values). Expect the right class, wrong instance — a sibling of the defect.

Point it at a claim the repo can contradict. **UNREFUTED means "not written down
anywhere I looked." It does not mean true.**
