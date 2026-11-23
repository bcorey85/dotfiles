---
name: orient
description: Explain how the current changes fit into the surrounding code that did NOT change, or walk an area of the repo as an ordered nvim walkthrough. Use after a coding phase to rebuild the mental map that diff review misses, or for "walk me through X", "show me how X works", "where does X live". Triggers on "orient", "situate this", "how does this fit", "what does this touch", "walk", "/orient", "/orient walk <area>".
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

After presenting, persist to `<vault>/orientations/<yyyy-mm-dd>-<repo>-<branch-or-scope>.md` (`$VAULT_DIR` else `~/vault`), headed by repo/branch/merge-base/date, + a capture line:
`~/.local/bin/note "orientation: <repo>/<branch> — [[<note filename without .md>]]"`. Same-day re-orient overwrites. `+ephemeral` skips.

## Walk — `/orient walk [focus]`

An ordered editor walkthrough of a feature, flow, symbol, file, dir or ticket (empty focus: the whole repo), stepped in nvim. Not for the current diff (use the default above).

1. Find the entry point (route, CLI command, keybinding, event handler, exported API, `main`). LSP where available, else `rg`.
2. Trace in execution order: entry, dispatch, core logic, data and side effects, output. Read every stop in full before writing its note. Skip tests, boilerplate and pass-through layers unless a test is the clearest statement of the contract.
3. Pick 5-15 stops, one anchor each, `<line>-<end>` covering only the lines that make the point, starting on a distinctive line. Several independent flows: walk the main one and list the rest as follow-up focus arguments. Whole repo: one stop per major dir's anchor file, the central domain module, then one request or command end to end.
4. Make one `nvim-jump` call with every stop in walk order, per `~/.claude/skills/_shared/nvim-jump.md`; each `--note` is 2-3 sentences (what the spot does, why, what it hands on). In chat: one sentence naming the flow, the numbered stops as `path:line — <note's first sentence>`, and "`]v`/`[v` steps the walk".
5. Save to `<vault>/walks/<repo>-<slug>.md` (`$VAULT_DIR` else `~/vault`; `+ephemeral` skips): the focus, `<repo> · <short sha> · <date>`, the flow sentence, then per stop `path:line-end — note` and `anchor: <first line of the range>`.

`/orient walk here [focus]` nests a deeper walk: no focus starts at the line under the nvim cursor (`nvim-jump --where`) and traces only what it calls; pass `--push` and end with "`[V` returns to the outer walk".
`/orient walk replay [name]` replays a saved walk (no name: list `<vault>/walks/<repo>-*.md`): `rg -n -F` each anchor, take the match nearest the saved line, shift the range by the offset; a gone file or anchor is stale. Present with the saved notes, skip stale stops, name them and offer a re-walk.

## Boundaries

- **Read-only — never edits** (vault persist and the saved walk write the vault only, never the repo).
- This is _not_ `/review` (correctness/bugs).
- Keep it tight. Refs over prose.
