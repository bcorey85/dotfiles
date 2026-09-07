# Editor follow (nvim-jump)

Any `file:line`-anchored walkthrough drives the editor to each anchor as presented.

```
nvim-jump <path>:<line>        # opens in the nvim whose cwd contains <path>
nvim-jump --list               # live instances and their cwd
```

Rules:

- **Once per item, before presenting.** Primary anchor first; rest stay `file:line`.
- **Exit 1 (no owner) is silent** — print `file:line`, keep going. Exit 2 (tool missing) stops jumping.
- **Never jump outside a presentation turn** — orchestrator only, while stepping a list.
- Paths are repo-relative; resolve against repo root (main checkout for `/peer-review` — worktrees own no nvim instance).
