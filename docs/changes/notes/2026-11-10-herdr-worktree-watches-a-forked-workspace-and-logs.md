---
type: "Change"
change_type: "fixed"
title: "herdr-worktree watches a forked workspace and logs the recovery steps when it closes"
description: "After `herdr-worktree --fork` starts the forked claude, a detached watcher checks the new workspace HERDR_WORKTREE_WATCH_SECONDS (default 120) after the fork starts; when the workspace is gone it writes the reopen and session-fork commands with literal paths to a log in the worktree's git dir and shows a herdr notification."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T18:24:23-06:00"}
seq: 4
kind: "fix"
components: ["script/herdr-worktree", "script/herdr-worktree-watch", "script/detach", "script/shell-command", "script/wait-loop-gate"]
evidence: ["forked-worktree-workspace-closes-about-a-minute"]
watches: []
test: "tests/scripts/test_herdr_worktree_watch.py::HerdrWorktreeWatchTest::test_a_gone_workspace_logs_two_numbered_steps_with_literal_values_and_no_shell_capture"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/.local/bin/herdr-worktree-watch <workspace> <worktree> <main checkout> <pane> <parent session>`: polls `herdr-api pane get` once a second for the fork's session id, bounded by `HERDR_WORKTREE_WATCH_SECONDS` (default 120), sleeps the rest of the wait, then runs `herdr-api workspace get`. An open workspace logs `still open`. A `workspace_not_found` reply logs two numbered steps with literal values: `1. herdr worktree open --cwd <main> --path <worktree> --focus` and `2. herdr-dev <worktree> <ws> <session> 'Go on with the work in this worktree; your brief is already in context.'`, then one line saying `<ws>` is the workspace id that step 1 prints (`.result.workspace.workspace_id`). The log holds no `ws=$(...)` capture and no `jq`. Under tuios step 1 is `herdr-api workspace create --cwd <worktree> --label <folder> --focus` and step 2 starts with `herdr-api workspace focus <ws> >/dev/null && `. The prompt is a resume prompt, never the original brief, which the fork already holds. When no session id showed, it logs step 1 and then `claude --resume` in the worktree as step 2. The log goes to `herdr-worktree-watch.log` in the worktree's git dir, and the watcher runs `herdr notification show` (not under tuios). Any other error logs the raw reply and exits 1. It never reopens the workspace itself.
- `herdr-worktree --fork`: starts the watcher detached once the fork pane shows claude, prints the watch line, and names the two recovery steps, the tuios variant and the `claude --resume` fallback in `--help`. A create reply with no workspace id exits 1 with `herdr-worktree: create reply has no workspace id: <reply>` before any pane or watcher command runs.
- `herdr-worktree` passes its own (parent) session id to the watcher as a 5th argument. The watcher keeps polling while the pane reports an empty id or that parent id, within the same bound, so the logged step 2 never re-forks the parent conversation. A pane that reports only the parent id by the end of the wait counts as no session id and logs the `claude --resume` fallback.
- The detached watcher's stdout and stderr go to `herdr-worktree-watch.log` (append) in place of `/dev/null`, so a failed detach or a watcher crash leaves its message there. The watcher writes its error messages to stderr, which the launcher sends to the log, so each line lands once and a direct run shows it.
- `tests/scripts/test_detach.py` reads the child's session id and pid with Python in place of `ps -o sid=`, which BSD and macOS `ps` lack.
- New `scripts/.local/bin/detach`: runs a command in its own session (`setsid`, else perl `POSIX::setsid` on macOS). `bookmark` and `research` use it in place of their own `setsid` line.
- `lib/shell_command.py` lists `detach` as a wrapper, and `gates/wait_loop_gate.py` adds `detach` to its detach words and deny message. The shell-write gate now reads `echo x | detach tee tracked.txt` as a write to `tracked.txt`, and a review-loop `detach make test` is denied like `setsid`, also behind `env A=1` or `nice` (`wrapper_chain`, which shares its peel loop with `command_after_wrappers`; both docstrings name the `WRAPPER_VALUE_OPTIONS` table). New cases in `tests/scripts/test_shell_command.py`, `test_shell_write_gate.py` and `test_wait_loop_gate.py`.
- Deploy: run `install/stow` so ~/.local/bin links the new `detach` and `herdr-worktree-watch`. Until then `herdr-worktree --fork`, `bookmark` and `research` stop with `<path> missing; run install/stow`. `bookmark` and `research` log the capture first, so they print `bookmark: logged to bookmarks.org, no source stub: <path> missing; run install/stow` and `research: logged to questions.org, no answer stub: <path> missing; run install/stow`.

## Evidence

Queue item: a forked worktree workspace closed about a minute after `herdr-worktree --fork` with no trace, and the user had to rebuild the reopen and session-fork commands by hand. The cause is unknown, so the change makes a close visible and names the recovery.

## Result

`tests/scripts/test_herdr_worktree_watch.py` (15 tests) and new cases in `tests/scripts/test_herdr_worktree.py` (27 tests in the file) fail before and pass after. `bash tests/run.sh` passes.

## Watch

None: the fix is pinned by tests; no intake number counts closed workspaces.

## Back-out

The change spans the commits from `6d3e125a` onward on branch `fix/coder-worktree-fixes`. Restore these files to their state before `6d3e125a` (`git checkout 6d3e125a^ -- <file>`, and `git rm` the files that did not exist then):

- `scripts/.local/bin/herdr-worktree`, `scripts/.local/bin/bookmark`, `scripts/.local/bin/research`
- `scripts/.local/bin/herdr-worktree-watch`, `scripts/.local/bin/detach` (new in `6d3e125a`; `detach` edited in `2d7b96f0` and `d0db0fc4`: remove both)
- `tests/scripts/test_herdr_worktree.py` (edited in several of those commits)
- `tests/scripts/test_herdr_worktree_watch.py` (new in `6d3e125a`: remove)
- `tests/scripts/test_detach.py` (new in `2d7b96f0`: remove)
- `tests/scripts/test_capture_scripts.py` (new: remove)
- `claude/.claude/scripts/lib/shell_command.py` (edited in `41c03629` and `e3d21041`), `claude/.claude/scripts/gates/wait_loop_gate.py` (edited in `41c03629`)
- `tests/scripts/test_shell_command.py`, `tests/scripts/test_shell_write_gate.py`, `tests/scripts/test_wait_loop_gate.py` (edited in `41c03629`)

Separately, revert the Phase 1 edits in `docs/plans/coder-worktree-fixes/acceptance-criteria.md`, `docs/plans/coder-worktree-fixes/plan.md`, `docs/changes/changelog.md` and `docs/changes/index.md`.
