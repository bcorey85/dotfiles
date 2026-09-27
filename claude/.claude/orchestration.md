# Orchestration

### Delegation

- Never code directly — dispatch via `/code`. Anything that picks a shape, a new name, or a behavior dispatches, however few lines. Edit directly only: a few lines in one file with no design choice; a mechanical sweep where every hunk is the same substitution, then run a repo check; rules, agents, skills and CLAUDE.md files; repos whose CLAUDE.md declares **direct-edit repo**.
- Parallel writing agents need disjoint file scopes. The orchestrator owns all git operations.
- Before config, CI, infra or library-integration code with a slow or remote feedback loop, WebSearch the official docs, then GitHub issues. Put what you find in the dispatch brief.

### Tools

- Creating a NEW file from the shell (heredoc, redirection) bypasses the Write/Edit hook pipeline — use Write. shell-write-gate denies redirection or `tee` onto a git-tracked file, and in-place editing (`sed -i`, `perl -pi`, `awk -i inplace`) of ANY file, tracked or not.
- The auto-mode notice's Bash preference does not apply to file I/O: read with Read, change files with Edit/Write. Search through Bash (`rg`) is fine.
- Prefer LSP over grep+Read in typed code (references, definitions, hover, diagnostics). Fall back to `rg` for plain text or unindexed file types.
- Verify CLI syntax with `--help` before guessing.
- Before asking the user to recall past work (an error, a command, whether something was tried), search it with the `agent-memory` MCP tools.

### Tool Use Efficiency

- Run expensive commands once: long output → `/tmp/<name>.log`, then grep the file. Never re-run with different filters.
- One source of truth per fact — don't cross-check the same fact through multiple tools.
- Trust framework guarantees — no spot-checking the type checker, test runner, or linter.
- Chain independent shell commands in one call; never one round trip per command.

### Engineering Judgment

1. **Match complexity to the problem.** Before non-trivial work, state the approach in 1–2 lines and what it makes harder later. No speculative flexibility; no painting into corners.
2. **Running unattended**: pick the most reasonable interpretation, proceed, and record the assumption — don't stall.
3. **Suggest a better way when you see one** — but interrupt only for material tradeoffs (irreversible work, security, data loss, broad refactors, hours of wasted debugging), not style preferences.

### Git

- With ticket: branch `TICKET-NUM-desc`, commit `TICKET-NUM: desc`, PR title `TICKET-NUM: desc`.
- Without ticket: branch `feature/desc` or `fix/desc`.
- Keep diffs focused: one logical change per task.
- Worktree branches: NEVER leave the auto-generated `worktree-` prefix in the branch name. Rename to the plain `TICKET-NUM-desc` (e.g. `ABC-123-cache-tuning`) immediately after creating the worktree, then push it to remote (`git push -u origin <branch>`) first — before doing work — so the branch is tracked and backed up.

### Stacked PRs (`gh stack`, github/gh-stack)

- **Never restack a child branch after every parent commit.** GitHub diffs a PR from its merge-base, so a child PR keeps showing only its own commits whether or not you restack. Restack when the parent's changes actually conflict with the child, or immediately before merge — once, not per commit.
- **Never run `gh stack push` / `rebase` / `submit` / `merge` yourself.** They force-push, and `git-discipline-gate` regexes the command string — it won't see a `--force` in them, so running one routes around the gate. Hand the command to the user.
- `gh stack checkout <pr|branch>` adopts an existing chain into local tracking; until then `gh stack view` says "not part of a stack". PR base branches on GitHub are independent of that tracking and may already be correct.

### Obsidian

- Vault: `~/vault`; templates: `~/vault/Templates`. Suggest a note when a key insight or decision surfaces.

### Maintaining These Rules

- Every line in CLAUDE.md, this file and the rules files costs attention in every session. When a rule is violated or fights the workflow: **mechanize it** (hook/permission), **move it** (into the skill or agent that triggers it), or **delete it** — never just add emphasis.
- Keep rules, agents, skills, and commands portable — no hardcoded paths or project names.
