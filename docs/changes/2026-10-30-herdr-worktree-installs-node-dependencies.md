---
type: "Change"
change_type: "fixed"
title: "herdr-worktree installs node dependencies in the new worktree"
description: "herdr-worktree runs npm ci or pnpm install --frozen-lockfile for each tracked lockfile at the worktree root or one folder down, before the panes start, so the first node tool run finds its modules."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T16:00:00-05:00"}
seq: 392
kind: "fix"
components: ["script/herdr-worktree", "rule/orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrWorktreeTest::test_a_new_worktree_gets_node_dependencies_for_each_lockfile_at_the_root_or_one_folder_down"
asked: ""
proof: []
unmeasured: "No intake number counts missing-module failures in a new worktree."
---

## Change

- After herdr (or git, under tuios) creates the worktree, `herdr-worktree` lists the tracked `package-lock.json` and `pnpm-lock.yaml` files at the root and one folder down. It runs `npm ci --no-audit --no-fund` or `pnpm install --frozen-lockfile` in each lockfile's folder before herdr-dev lays out the panes.
- Install output goes to `herdr-worktree-install.log` in the worktree's git dir, not to the 3-line ctrl+w popup. One `installing dependencies in <folder>` line on stderr comes before each install, so a slow install does not look hung. The installer reads `/dev/null`, so it cannot consume the lockfile list.
- When the installer is not on PATH or the install fails, it warns with the folder and the command, and the run goes on. A failed install's warning also names the log.
- `orchestration.md` tells a session to run `herdr-worktree --fork` with a Bash `timeout` of 600000, so a slow install does not end the run before the fork starts.
- The test stub for `herdr worktree create` now makes the worktree with git, as herdr does.

## Evidence

A queue item reported that the first make target that ran node tooling in a new worktree failed with a missing-module error. That cost a failed background run and a retry. The real repos hold three lockfile shapes: a root `package-lock.json`, a root `pnpm-lock.yaml`, and `frontend/pnpm-lock.yaml`.

## Result

`test_a_new_worktree_gets_node_dependencies_for_each_lockfile_at_the_root_or_one_folder_down` and `test_a_failed_install_warns_with_the_command_and_the_run_goes_on` fail before the change and pass after it. So do `test_an_installer_that_reads_stdin_does_not_swallow_the_remaining_lockfiles`, `test_install_output_goes_to_the_log_and_a_clean_install_prints_no_log_path` and `test_each_install_prints_one_progress_line`. The existing herdr-worktree tests still pass.

## Watch

None.

## Back-out

Revert the commit.
