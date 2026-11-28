# Research Questions

1. How does `scripts/.local/bin/hunk-review-pane` launch the `hunk diff --watch` process, and how does `herdr-dev` start it? Trace the command line from the herdr entry point to the final exec, including any wrapper or environment setup.
2. How does `claude/.claude/scripts/tools/lane_status.py` gather and report per-lane and per-process information such as memory use and open lanes? What data sources, output formats and thresholds does it use?
3. How do existing scripts under `scripts/.local/bin` handle platform differences, such as the presence or absence of `systemd-run`, `systemctl --user` or macOS tools? Which shared defaults live in `scripts/.local/lib`?
4. How does `scripts/.local/bin/herdr-lane-resume` parse its `--close <name>` argument, read the lane file, and look up lanes? What does it do when no lane file entry matches, and how does it remove the worktree, prune and delete the branch?
5. How can herdr workspaces be listed and what fields (checkout path, name, id) do they expose? How do `herdr-api`, `herdr-worktree` and `herdr-worktree-prune` read them, and how do they check whether a branch is merged?
6. What does `install/check-script-links` check, what does it print and exit with, and what calls it today? How does `install/stow` relink the `scripts` package?
7. What does the `.githooks` directory hold, how is `core.hooksPath` set, and which git hook types exist or are referenced anywhere in the repo? Is there a pull helper such as `pull_keep_index.py`, and what does it do after a pull or merge?
8. How does `zsh/.zshrc` define the `ls` alias and the `CLAUDECODE` guard, and what other aliases, functions or init code differ between interactive shells, agent shells and Claude Code shell snapshots?
9. What test patterns exist under `tests/` and `tests/scripts/` for shell scripts in `scripts/.local/bin`, for git hooks, and for zsh or doctor-style probes? How do they fake external commands such as herdr, and how does `tests/run.sh` pick them up?
10. How are change files created and stored (`~/agent-evals/bin/build_changes.py`), and what format do existing change files follow?

## Exploration Map

- `scripts/.local/bin/hunk-review-pane` — launcher of the diff viewer pane
- `scripts/.local/bin/herdr-dev` — starts the pane for each lane
- `claude/.claude/scripts/tools/lane_status.py` — lane and memory reporting
- `scripts/.local/bin/herdr-lane-resume` — lane close and resume logic
- `scripts/.local/bin/herdr-worktree`, `scripts/.local/bin/herdr-worktree-prune`, `scripts/.local/bin/herdr-api` — workspace listing and merged-branch checks
- `scripts/.local/lib/` — shared sourced defaults
- `install/check-script-links`, `install/stow` — script link checking and stowing
- `.githooks/` — existing git hooks
- `claude/.claude/scripts/tools/pull_keep_index.py` — pull helper
- `zsh/.zshrc` — alias and shell setup
- `tests/` and `tests/scripts/` — test conventions and runner
- `docs/toolkit-script-rules.md` — rules for toolkit scripts
