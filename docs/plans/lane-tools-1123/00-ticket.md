# lane-tools-1123: lane viewer memory cap, lane close without an entry, script links after a merge, ls probe

Source: ~/agent-evals/queue/lane-diff-viewer-pane-grows-without-bound-and-eats.md
Source: ~/agent-evals/queue/herdr-lane-resume-close-refuses-a-merged-lane-that.md
Source: ~/agent-evals/queue/a-merge-that-adds-a-script-under-local-bin-leaves.md
Source: ~/agent-evals/queue/ls-t-still-runs-eza-in-agent-shells-after-the.md

Source: four ~/agent-evals queue items (claimed). Their Done-when text is the contract.

## 1. lane-diff-viewer-pane-grows-without-bound-and-eats (scripts/.local/bin/hunk-review-pane, claude/.claude/scripts/tools/lane_status.py)

Context: each herdr lane opens a `hunk diff --watch` pane (hunk-review-pane, started by herdr-dev). After 18 hours one viewer held 4.2 GB RSS, a second 2.9 GB; ten viewers held about 11 GB of 30 GB with swap full. The orchestrator could not stop them, so the user had to.

Done when: The lane viewer starts under a memory cap (for example systemd-run --user --scope -p MemoryMax=1G) or restarts itself past a size, and lane-status names a viewer over the cap. A test starts the launcher and asserts the cap is on the command.

## 2. herdr-lane-resume-close-refuses-a-merged-lane-that (scripts/.local/bin/herdr-lane-resume)

Context: two merged lanes opened before the lane file existed. For each, `--close` answered "no lane named ...", and the orchestrator listed workspaces, matched the worktree path, then removed the worktree, pruned and deleted the branch by hand.

Done when: close with a lane name or worktree path that has no lane file entry finds the herdr workspace whose checkout path matches, checks the branch is merged, and closes it. A test with an empty lane file and a fake herdr workspace list passes.

## 3. a-merge-that-adds-a-script-under-local-bin-leaves (.githooks, install/check-script-links)

Context: after a lane merge reached master, herdr-lane-resume and lane-status were not linked from ~/.local/bin, so the documented close command failed with command not found. install/check-script-links exists and named both, but nothing ran it after the merge. The fix was `stow -R scripts` from ~/dotfiles. The repo already sets core.hooksPath=.githooks (it holds pre-commit).

Done when: A git post-merge hook (or the pull helper) runs check-script-links and restows the scripts package when it reports a gap. A test adds a script on a branch, merges it, and asserts the link exists.

## 4. ls-t-still-runs-eza-in-agent-shells-after-the (zsh/.zshrc)

Context: on 2026-11-22 two agent shell calls using `ls -t` failed with eza's "invalid value for --time"; `command ls` worked. zsh/.zshrc defines `alias ls="eza --icons=auto"` only when CLAUDECODE is unset (commit 261942676, 2026-11-22 16:08). Every Claude Code shell snapshot in ~/.claude/shell-snapshots written after 16:08 lacks the ls alias; every one before it holds it, so the failures came from sessions whose snapshot predates the guard. Today `type ls` in a Claude Code Bash call prints `/usr/bin/ls`.

Done when:
- In a Claude Code Bash call, type ls resolves to the system ls.
- A test or doctor check runs that probe and fails when ls is an alias or function.
- Deletes: nothing.

## Constraints

- Everything works on WSL, Ubuntu, macOS and Arch (repo CLAUDE.md). systemd-run is absent on macOS: the viewer runs uncapped there or uses a portable restart.
- Toolkit scripts under claude/.claude/scripts follow docs/toolkit-script-rules.md; shared script defaults live in a sourced file under scripts/.local/lib.
- Tests go in tests/scripts/test_<script>.py. Each behavior change gets a change file (python3 ~/agent-evals/bin/build_changes.py new).
- Do not touch mutation-tester, refactor or calibration files, or claude/.claude/scripts/review.
