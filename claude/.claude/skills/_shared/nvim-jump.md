# Editor follow (nvim-jump, hunk-notes)

Any `file:line`-anchored walkthrough drives the user's view to each anchor as presented. Pick the command by what the walk shows:

- **`nvim-jump`** for planning and decision walks (research, drill-downs, `/walk`, `/drive`, `/peer-review`): it opens the file in nvim. With no nvim owning the file, inside herdr it turns the tab's `review` pane (`hunk-review-pane`) into nvim in the repo root and jumps there.
- **`hunk-notes`** for phase-end and review walks over the main checkout diff (`/stage`, `/verify-branch`, review asks): the review pane diffs against the branch base on a feature branch, so committed lines anchor too, but a note lands only on a line the diff shows. It posts the list as agent notes in the repo's live hunk session and focuses the first. Same arguments as `nvim-jump`; there is no `--push` and no `]v`/`[v`.

```
nvim-jump  --note "TEXT" <path>:<line>[-<end>] [--note "TEXT" <path>:<line>[-<end>] ...]
                               # opens the first in the nvim whose cwd contains it; ]v/[v step the rest
                               # exit 1: no such directory, or no nvim owns the file and no review pane for its repo could open one, or nvim did not start in time
                               # exit 2: bad args
hunk-notes --note "TEXT" <path>:<line>[-<end>] [--note "TEXT" <path>:<line>[-<end>] ...]
                               # exit 1: file not in a git repo, no live hunk session for the repo, hunk cannot show the file, or no such directory
                               # exit 2: bad args, or hunk missing
```

Rules (both commands):

- **One call per item, before presenting.** It carries every anchor the item cites, primary first. A set presented together (a reading queue, an ask list, an evidence table) is one call, one anchor per entry, in presented order.
- **Each anchor gets a one-line `--note`** before it, saying what that spot shows for the item. `<line>-<end>` covers only the lines that make the point.
- **`hunk-notes` summary shows fewer posted than listed** (`k/N notes`): print the `not posted: file:line` anchors it lists as `file:line`.
- **Exit 1 is silent** — print the anchors as `file:line`, keep going. Exit 2 (bad args, or hunk missing for `hunk-notes`) stops jumping.
- **Never jump outside a presentation turn** — orchestrator only, while stepping a list.
- Paths are repo-relative; resolve against repo root (main checkout for `/peer-review` — worktrees own no nvim instance).
