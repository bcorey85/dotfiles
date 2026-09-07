---
paths: []
---

# Git

- With ticket: branch `TICKET-NUM-desc`, commit `TICKET-NUM: desc`, PR title `TICKET-NUM: desc`.
- Without ticket: branch `feature/desc` or `fix/desc`.

## Stacked PRs (`gh stack`, github/gh-stack)

- **Never restack a child branch after every parent commit.** GitHub diffs a PR from its merge-base, so a child PR keeps showing only its own commits whether or not you restack. Restack when the parent's changes actually conflict with the child, or immediately before merge — once, not per commit.
- **Never run `gh stack push` / `rebase` / `submit` / `merge` yourself.** They force-push, and `git-discipline-gate` regexes the command string — it won't see a `--force` in them, so running one routes around the gate. Hand the command to the user.
- `gh stack checkout <pr|branch>` adopts an existing chain into local tracking; until then `gh stack view` says "not part of a stack". PR base branches on GitHub are independent of that tracking and may already be correct.
