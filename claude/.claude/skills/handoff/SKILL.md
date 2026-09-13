---
name: handoff
description: Write the session's state to HANDOFF.md at the repo root so the next conversation starts from disk after /clear. Use at a task boundary, before the context grows large enough to auto-compact. User-invoked only, "/handoff".
disable-model-invocation: true
allowed-tools: [Bash, Read, Write]
---

# Handoff — write the state down, then the user clears

A coding lane already has its state on disk: the plan, the decision ledger, the branch recap. This skill is for the sessions that do not: toolkit edits, research, measurement, freeform work.

## Step 1: Gather

Take the state from the conversation. Run `git status --short` and `git log --oneline -5` for the commit hashes and the untracked files. Do not scan the codebase. Do not dispatch an agent.

## Step 2: Write `HANDOFF.md` at the repo root

If a `HANDOFF.md` already exists, read it first. Carry every item that is still open into the new file. The file stays untracked. Never `git add` it.

```
# Handoff — <date>

Written to end the session at a task boundary. Untracked. Delete when the next session absorbs it.

## Done
- <what shipped: the change, the commit hash, the file paths>

## Numbers to keep            (omit when there are none)
- <every measured figure the next step needs>

## Decided
- <the decision, and the reason when it is not obvious>

## Not decided
- <open item, in the order the next session must take them, with the recommendation if there is one>

## Rules that apply to the next step
- <the repo or toolkit rules the next step must obey: ledger rows, provenance limits, commit trailers>

## Files to reopen
- <path — why>
```

Rules for the content:

- Write facts, not narrative. A reader with no memory of the session must be able to act on it.
- A number that lives only in the conversation is lost at `/clear`. Write every number the next step depends on. Leave out every number it does not.
- Name files by path and commits by hash. Never use a name coined during the session.
- Keep the file under about 60 lines. The next session reads it on its first turn, and every line costs there.

## Step 3: Hand back

Print the resume line, then stop:

```
Wrote HANDOFF.md (<n> lines). Now run /clear, then:
  read HANDOFF.md and continue with <the first item under Not decided>.
```

Never run `/clear` yourself. Never commit. Never delete the file.

## Not this skill

- `/todos` — a conversational action list, nothing on disk.
- `/branch-recap` — the branch's process residue before a PR.

## Arguments

`$ARGUMENTS`, when given, names the item the next session must take first. Put it at the top of **Not decided**.
