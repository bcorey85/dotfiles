# Research Questions

1. How does `claude/.claude/scripts/tools/herdr-worktree` work end to end? Trace what it creates, records and prints from invocation through workspace creation, and what happens on `--fork` and when a forked workspace closes.
2. What state does the herdr worktree tooling persist today, and where? Cover any lane files, logs, recovery-step records, and where they sit relative to a worktree.
3. How do `scripts/.local/bin/herdr-worktree-prune` and its `--apply` and `--branches` modes decide a worktree is merged and clean, and which existing steps (merge lines, session start, hooks, timers) currently invoke it or any other worktree cleanup?
4. How does `scripts/.local/bin/herdr-phase-change` work? Trace how it finds its target agent or pane, how it sends `/clear` and then a prompt, and what identity of the sending session is available to it.
5. How do `herdr agent list`, `herdr-api`, and the ListAgents output identify agents (session name, pane id, worktree path, agent_status), and what do they return when a target is not found?
6. How does `scripts/.local/bin/hunk-review-pane` start, which herdr pane or label variables (`HERDR_PANE_ID` and similar) does it use, and how do `herdr-dev` and `nvim-jump` set and look up the pane label `review`?
7. How does `claude/.claude/scripts/tools/pull_keep_index.py` work? Trace the save commit, pull, and re-apply of staged and unstaged changes, including its options.
8. Which existing scripts print status or state information, and what are their invocation forms?
9. What test patterns exist under `tests/scripts/` for the herdr scripts, `pull_keep_index.py` and other tools scripts? Cover how external commands are stubbed, how script paths are resolved through `toolkit_paths.py`, and how `tests/run.sh` and `tests/lint.sh` run them.
10. How do scripts under `claude/.claude/scripts/tools/` and `scripts/.local/bin/` handle errors and exit codes, and which `lib/` modules do they import?
11. In `pull_keep_index.py`, what exactly is saved before the pull and what is left in the tree during the pull? Cover how it detects dirty or staged files, whether it records which files exist or change during the run, and what it checks before it starts.
12. What does `pull_keep_index.py` do when the re-apply or `--put-back` step fails? Cover which refs, commits or messages it leaves behind, whether a save commit is reachable from a named ref, and what recovery text it prints.

## Exploration Map

- `claude/.claude/scripts/tools/herdr-worktree` — lane creation, fork and close handling
- `claude/.claude/scripts/tools/pull_keep_index.py` — pull with staged-file preservation
- `scripts/.local/bin/herdr-worktree-prune` — worktree prune tool
- `scripts/.local/bin/herdr-phase-change` — phase change prompt delivery
- `scripts/.local/bin/hunk-review-pane` — review pane start
- `scripts/.local/bin/nvim-jump` and `scripts/.local/bin/herdr-api` — pane lookup by label and herdr API access
- `claude/.claude/scripts/lib/` — shared modules
- `tests/scripts/` and `tests/run.sh` — test patterns and runner
- `docs/glossary.md` — canonical domain terms
