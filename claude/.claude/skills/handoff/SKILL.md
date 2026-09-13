---
name: handoff
description: Write the session's state to a handoff file outside the repo, keyed by checkout and terminal, so the next conversation starts from disk after /clear. "/handoff" writes, "/handoff resume" reads. Use at a task boundary, before the context grows large enough to auto-compact. User-invoked only.
disable-model-invocation: true
allowed-tools: [Bash, Read, Write]
---

# Handoff — write the state down, then the user clears

A coding lane already has its state on disk: the plan, the decision ledger, the branch recap. This skill is for the sessions that do not: toolkit edits, research, measurement, freeform work.

Nothing is written inside the repo. The file lives under `$XDG_STATE_HOME/claude-handoff/`, keyed by the checkout and by the terminal, so two sessions in one checkout do not collide and the path survives `/clear`. Always take the path from the helper:

```bash
bash "${CLAUDE_SKILL_DIR}/handoff-path"        # this checkout, this terminal
bash "${CLAUDE_SKILL_DIR}/handoff-path" list   # every handoff for this checkout, newest first
```

## `/handoff` — write

### Step 1: Gather

Take the state from the conversation. Run `git status --short` and `git log --oneline -5` for the commit hashes and the untracked files. Do not scan the codebase. Do not dispatch an agent.

### Step 2: Write the file

If a file already exists at the path, read it first. Carry every item that is still open into the new file.

```
# Handoff — <date>

Written to end the session at a task boundary. Delete when the next session absorbs it.

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

### Step 3: Hand back

Print the resume line, then stop:

```
Wrote <path> (<n> lines). Now run /clear, then: /handoff resume
```

Never run `/clear` yourself. Never commit. Never write inside the repo.

## `/handoff resume` — read

1. Run the helper. If the file exists, read it.
2. If it does not exist, run `list`. One file: read it. Several: show their paths and dates, then ask which. None: say so and stop.
3. Continue with the first item under **Not decided**, unless the arguments name another item.
4. When every item in the file is absorbed, delete the file with `rm`.

## Not this skill

- `/todos` — a conversational action list, nothing on disk.
- `/branch-recap` — the branch's process residue before a PR.

## Arguments

`$ARGUMENTS`. `resume [item]` reads. Any other text names the item the next session must take first: put it at the top of **Not decided**.
