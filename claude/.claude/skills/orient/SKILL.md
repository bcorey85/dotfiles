---
name: orient
description: Explain how the current changes fit into the surrounding code that did NOT change. Use after a coding phase to rebuild the mental map that diff review misses. Triggers on "orient", "situate this", "how does this fit", "what does this touch", "/orient".
---

# Orient — situate the change in its unchanged surroundings

Run after a coding phase, before committing, when the diff doesn't convey structure. **On-demand, never a phase — no gate runs it.**

## Scope

Default target depends on where you are:

- **Feature branch** — the WHOLE branch (merge-base vs default, covers worktree).
- **Default branch** — worktree changes only.

Or orient around `$ARGUMENTS` (file/dir/symbol/feature) instead of the diff.

```
$ARGUMENTS
```

## Method — do NOT just read the diff

1. **Get the changed surface.** On a feature branch:
   `BASE=$(git merge-base HEAD origin/master 2>/dev/null || git merge-base HEAD origin/main)`,
   then `git diff --stat "$BASE"`/`git diff "$BASE"` (committed phases AND worktree). Default branch: same against HEAD.
   This is the only step that looks at the diff.

2. **Now read the unchanged neighbors** — changed symbols _in full, in place_, plus:
   - Callers (who invokes, with what assumptions).
   - New callees (what it now reaches into).
   - Untouched siblings in the same module.
   - Helpers it _should_ have reused.
     LSP where available, else `rg`. Whole functions, not hunks.

3. **Build the map**, then report it concisely:

   ### Where it sits

   One paragraph: module/layer + role in the existing structure.

   ### Wiring (changed ↔ unchanged)

   Real connections (`caller → changed → callee`, `file:line`): how it's reached, what it reaches.

   ### Reused vs. new

   Reused abstractions vs fresh introductions; flag new-that-duplicates.

   ### Structural risks (the diff can't show these)

   Only if real:
   - Duplication an existing helper covers.
   - Wrong layer (handler logic belonging in a service).
   - Broken invariant in an unchanged neighbor.
   - Inconsistent pattern vs siblings.
     None → say so; don't manufacture.

   ### Attention map (where to spend review time)

   Changed files by blast radius (from wiring, never diff size). One line per file: `path — rank rationale`. Rank by:

   - **Inbound references** (LSP count of unchanged callers).
   - **Enforcement surface** (hooks, gates, auth, privileged/outside-repo writes).
   - **Contract exposure** (exported/public vs leaf/internal).
   - **Reversibility** (alias fix vs system-config write).

   Tests/docs/lockfiles sink unless wiring says otherwise. USER attention only — never into reviewer dispatches (pre-labels anchor skimming where quiet bugs survive).

## Persist to vault (default — `+ephemeral` skips)

After presenting, persist to `<vault>/Orientations/<yyyy-mm-dd>-<repo>-<branch-or-scope>.md` (`$VAULT_DIR` else `~/vault`), headed by repo/branch/merge-base/date, + capture line for `/daily-recap`:
`~/.local/bin/note "orientation: <repo>/<branch> — [[<note filename without .md>]]"`. Same-day re-orient overwrites. `+ephemeral` skips.

## Boundaries

- **Read-only — never edits** (vault persist writes vault-only, never repo).
- This is _not_ `/review` (correctness/bugs).
- Keep it tight. Refs over prose.
