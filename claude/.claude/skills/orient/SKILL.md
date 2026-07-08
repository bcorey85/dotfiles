---
name: orient
description: Explain how the current changes fit into the surrounding code that did NOT change. Use after a coding phase to rebuild the mental map that diff review misses. Triggers on "orient", "situate this", "how does this fit", "what does this touch", "/orient".
---

# Orient — situate the change in its unchanged surroundings

Diff review shows hunks. It cannot show how those hunks connect to the code that
stayed the same — so reviewing diffs builds a model of _changes_, never a model of
the _system_. This skill closes that gap. Run it after a coding phase, before
committing, when you've read the diff but don't feel the structure.

## Scope

Default target depends on where you are:

- **On a feature branch** — the WHOLE branch: merge-base diff vs the default branch,
  which also covers the working tree. By orient time most phases are usually already
  committed; `git diff HEAD` alone would silently orient around the last uncommitted
  sliver.
- **On the default branch** — working-tree changes (staged + unstaged) only.

The user may instead pass a file, directory, symbol, or feature name in `$ARGUMENTS` — if so,
orient around that instead of the diff.

```
$ARGUMENTS
```

## Method — do NOT just read the diff

1. **Get the changed surface.** On a feature branch:
   `BASE=$(git merge-base HEAD origin/master 2>/dev/null || git merge-base HEAD origin/main)`,
   then `git diff --stat "$BASE"` and `git diff "$BASE"` (covers committed phases AND the
   working tree). On the default branch: `git diff --stat HEAD` then `git diff HEAD`.
   This is the only step that looks at the diff.

2. **Now read the unchanged neighbors.** This is the whole point — open the actual
   files and read the changed symbols _in full, in place_, plus:
   - The callers of every new/changed function (who invokes it, with what assumptions).
   - The callees it newly depends on (what it now reaches into).
   - Sibling code in the same module/file it sits beside but didn't touch.
   - Any existing helper/abstraction it _should_ have reused.
     Use LSP (references / definition / hover) when the language has a server; fall back
     to `rg` for plain text. Read whole functions, not hunks.

3. **Build the map**, then report it concisely:

   ### Where it sits

   One short paragraph: what module/layer this change lives in and what role it plays
   in the existing structure.

   ### Wiring (changed ↔ unchanged)

   A short list of the real connections — `caller → changed symbol → callee`, with
   `file_path:line` refs. Show how the new code is reached and what it reaches.

   ### Reused vs. new

   What existing abstractions it correctly reused, and what it introduced fresh.
   Flag anything new that duplicates something that already exists.

   ### Structural risks (the diff can't show these)

   Call out, only if real:
   - New code that **duplicates** logic an existing helper already provides.
   - A change at the **wrong layer** (logic in a handler that belongs in a service, etc.).
   - A **broken assumption / invariant** in an unchanged neighbor two files away.
   - An **inconsistent pattern** vs. how siblings do the same thing.
     If there are none, say so plainly — don't manufacture findings.

## Persist to vault (default — `+ephemeral` skips)

After presenting the report, persist it to the vault (root: `$VAULT_DIR` if set, else
`~/vault`): write the full orientation to
`<vault>/Orientations/<yyyy-mm-dd>-<repo>-<branch-or-scope>.md`, headed by repo,
branch, merge-base sha, and date. Then append a capture line so tonight's
/daily-recap links it:
`~/.local/bin/note "orientation: <repo>/<branch> — [[<note filename without .md>]]"`.
Re-orienting the same repo+branch same day overwrites the note (latest map wins).
With `+ephemeral`, skip both writes.

## Boundaries

- **Read-only. Never edit.** This rebuilds understanding; it does not change code.
  (The default vault persist writes only under the vault — never in the repo.)
- This is _not_ `/review` (correctness/bugs).
  It answers one question: **how does this change relate to the code around it?**
- Keep it tight. Refs over prose. The goal is to reload the user's mental map fast,
  not to write an essay.
