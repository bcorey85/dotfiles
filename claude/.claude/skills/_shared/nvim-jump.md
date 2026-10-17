# Editor follow (nvim-jump)

Any `file:line`-anchored walkthrough drives the editor to each anchor as presented.

```
nvim-jump --note "TEXT" <path>:<line>[-<end>] [--note "TEXT" <path>:<line>[-<end>] ...]
                               # opens the first in the nvim whose cwd contains it; ]k/[k step the rest
nvim-jump --list               # live instances and their cwd
```

Rules:

- **One call per item, before presenting.** It carries every anchor the item cites, primary first. A set presented together (a reading queue, an ask list, an evidence table) is one call, one anchor per entry, in presented order.
- **Each anchor gets a one-line `--note`** before it, saying what that spot shows for the item. `<line>-<end>` covers only the lines that make the point.
- **Exit 1 (no owner) is silent** — print the anchors as `file:line`, keep going. Exit 2 (tool missing) stops jumping.
- **Never jump outside a presentation turn** — orchestrator only, while stepping a list.
- Paths are repo-relative; resolve against repo root (main checkout for `/peer-review` — worktrees own no nvim instance).
