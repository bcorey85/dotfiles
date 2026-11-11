---
type: "Change"
change_type: "fixed"
title: "herdr-worktree watches a forked workspace and logs the recovery steps when it closes"
description: "After `herdr-worktree --fork` starts the forked claude, a detached watcher checks the new workspace HERDR_WORKTREE_WATCH_SECONDS (default 120) after the fork starts; when the workspace is gone it writes the reopen and session-fork commands with literal paths to a log in the worktree's git dir and shows a herdr notification."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T18:24:23-06:00"}
seq: 4
kind: "fix"
components: ["script/herdr-worktree", "script/herdr-worktree-watch", "script/detach"]
evidence: ["forked-worktree-workspace-closes-about-a-minute"]
watches: []
test: "tests/scripts/test_herdr_worktree_watch.py::HerdrWorktreeWatchTest::test_a_gone_workspace_logs_literal_worktree_checkout_session_and_placeholder_workspace_id_prompt"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/.local/bin/herdr-worktree-watch <workspace> <worktree> <main checkout> <pane>`: polls `herdr-api pane get` once a second for the fork's session id, bounded by `HERDR_WORKTREE_WATCH_SECONDS` (default 120), sleeps the rest of the wait, then runs `herdr-api workspace get`. An open workspace logs `still open`. A `workspace_not_found` reply logs `herdr worktree open --cwd <main> --path <worktree> --focus` (under tuios, `herdr-api workspace create`) and `herdr-dev <worktree> <new workspace id> <session> "<prompt>"`, or `claude --resume` when no session id showed, to `herdr-worktree-watch.log` in the worktree's git dir, and runs `herdr notification show` (not under tuios). Any other error logs the raw reply and exits 1. It never reopens the workspace itself.
- `herdr-worktree --fork`: starts the watcher detached once the fork pane shows claude, prints the watch line, and names both recovery steps in `--help`.
- New `scripts/.local/bin/detach`: runs a command in its own session (`setsid`, else perl `POSIX::setsid` on macOS). `bookmark` and `research` use it in place of their own `setsid` line.

## Evidence

Queue item: a forked worktree workspace closed about a minute after `herdr-worktree --fork` with no trace, and the user had to rebuild the reopen and session-fork commands by hand. The cause is unknown, so the change makes a close visible and names the recovery.

## Result

`tests/scripts/test_herdr_worktree_watch.py` (11 tests) and new cases in `tests/scripts/test_herdr_worktree.py` (22 tests in the file) fail before and pass after. `bash tests/run.sh` passes.

## Watch

None: the fix is pinned by tests; no intake number counts closed workspaces.

## Back-out

Revert commit `6d3e125a` on branch `fix/coder-worktree-fixes`.
