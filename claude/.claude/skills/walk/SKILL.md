---
name: walk
description: Walk the user through a feature, area, or whole repo as an ordered editor walkthrough — each stop a file:line with a one-line note, stepped in nvim. Use for "walk", "walk me through", "show me how X works", "where does X live", "/walk <area>". Not for the current diff (that is /orient).
---

# Walk — an ordered nvim-jump walkthrough

```
$ARGUMENTS
```

The argument names the focus: a feature, flow, symbol, file, dir or ticket. Empty → whole-repo walk.

## Method

1. **Find the entry point.** Where the focus is triggered: route, CLI command, keybinding, event handler, exported API, `main`. LSP where available, else `rg`.
2. **Trace in execution order.** Entry → dispatch → core logic → data and side effects → output. Follow real calls; read every stop in full before writing its note. Include the config or wiring that decides behavior. Skip tests, boilerplate and pass-through layers unless a test is the clearest statement of the contract.
3. **Pick 5–15 stops.** One anchor each, `<line>-<end>` covering only the lines that make the point. Start each range on a distinctive line (a definition, key, heading or comment), never a bare brace.
4. **Several independent flows in the focus** → walk the main one; list the rest as follow-up `/walk` arguments.

Whole-repo walk: top-level layout (one stop per major dir's anchor file), the central domain module, then one representative request or command end to end.

## Present

1. One `nvim-jump` call with every stop in walk order, per `~/.claude/skills/_shared/nvim-jump.md`. Each `--note` says what the spot does and what it hands to the next stop.
2. Then in chat: one sentence naming the flow, the numbered stops as `path:line — note` in the same order, and "`]k`/`[k` steps the walk".

## Save (default — `+ephemeral` skips)

After presenting, write `<vault>/Walks/<repo>-<slug>.md` (`$VAULT_DIR` else `~/vault`; slug from the focus). Same name overwrites.

```
# <focus>

<repo> · <short sha> · <yyyy-mm-dd>

<the one-sentence flow>

1. `path:line-end` — note
   anchor: `<first line of the range, trimmed>`
```

## Replay — `/walk replay [name]`

No name → list `<vault>/Walks/<repo>-*.md`. Otherwise, per saved stop: `rg -n -F` the anchor in its path, take the match nearest the saved line, and shift the range by the same offset. File or anchor gone → stale. Present as above with the saved notes, skipping stale stops; then name the stale ones and offer to re-walk them and re-save.

## Boundaries

- Read-only on the repo. The only write is the saved walk in the vault.
- No review: no bugs, smells or suggestions unless asked.
