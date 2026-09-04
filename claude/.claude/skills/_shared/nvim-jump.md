# Editor follow (nvim-jump)

Any walkthrough that presents items anchored to a `file:line` — a review finding, a
research section, a `/stage` read-queue entry — drives the user's editor to the anchor
as each item is presented, so the user reads the code instead of retyping the path.

```
nvim-jump <path>:<line>        # opens in the nvim whose cwd contains <path>
nvim-jump --list               # live instances and their cwd
```

Rules:

- **Once per item, before presenting it.** Jump to the item's primary anchor, then give
  the prose. If an item has several anchors, jump to the first; the rest stay `file:line`
  in the text and the user asks to jump if they want.
- **Exit 1 (no instance owns the file) is silent.** Print the `file:line` as usual and
  keep going — do not retry, do not tell the user to open nvim. Exit 2 means the tool is
  missing; stop jumping for the rest of the walkthrough.
- **Never jump outside a presentation turn.** Reviewers, coders, and research agents do
  not call it — only the orchestrator, only while stepping the user through a list.
- Paths are repo-relative in the doc; resolve against the repo root (or the worktree, for
  `/peer-review`) before calling. A worktree has no nvim instance of its own — pass the
  path under the main checkout so the user's editor, not the worktree, is what moves.
