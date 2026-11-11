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

- New `scripts/.local/bin/herdr-worktree-watch <workspace> <worktree> <main checkout> <pane>`: polls `herdr-api pane get` once a second for the fork's session id, bounded by `HERDR_WORKTREE_WATCH_SECONDS` (default 120), sleeps the rest of the wait, then runs `herdr-api workspace get`. An open workspace logs `still open`. A `workspace_not_found` reply logs `herdr worktree open --cwd <main> --path <worktree> --focus` (under tuios, `herdr-api workspace create`) and `herdr-dev <worktree> <new workspace id> <session> 'Go on with the work in this worktree; your brief is already in context.'` (a resume prompt, never the original brief, which the fork already holds), or `claude --resume` when no session id showed, to `herdr-worktree-watch.log` in the worktree's git dir, and runs `herdr notification show` (not under tuios). Any other error logs the raw reply and exits 1. It never reopens the workspace itself.
- `herdr-worktree --fork`: starts the watcher detached once the fork pane shows claude, prints the watch line, and names both recovery steps in `--help`.
- New `scripts/.local/bin/detach`: runs a command in its own session (`setsid`, else perl `POSIX::setsid` on macOS). `bookmark` and `research` use it in place of their own `setsid` line.
- Deploy: run `install/stow` so ~/.local/bin links the new `detach` and `herdr-worktree-watch`. Until then `herdr-worktree --fork`, `bookmark` and `research` stop with `<path> missing; run install/stow`. `bookmark` and `research` log the capture first, so they print `bookmark: logged to bookmarks.org, no source stub: <path> missing; run install/stow` and `research: logged to questions.org, no answer stub: <path> missing; run install/stow`.

## Evidence

Queue item: a forked worktree workspace closed about a minute after `herdr-worktree --fork` with no trace, and the user had to rebuild the reopen and session-fork commands by hand. The cause is unknown, so the change makes a close visible and names the recovery.

## Result

`tests/scripts/test_herdr_worktree_watch.py` (13 tests) and new cases in `tests/scripts/test_herdr_worktree.py` (25 tests in the file) fail before and pass after. `bash tests/run.sh` passes.

## Watch

None: the fix is pinned by tests; no intake number counts closed workspaces.

## Back-out

The change spans the commits from `6d3e125a` onward on branch `fix/coder-worktree-fixes`. Restore these files to their state before `6d3e125a` (`git checkout 6d3e125a^ -- <file>`, and `git rm` the files that did not exist then):

- `scripts/.local/bin/herdr-worktree`, `scripts/.local/bin/bookmark`, `scripts/.local/bin/research`
- `scripts/.local/bin/herdr-worktree-watch`, `scripts/.local/bin/detach` (new in `6d3e125a`; `detach` rewritten in `2d7b96f0`: remove both)
- `tests/scripts/test_herdr_worktree.py` (edited in several of those commits)
- `tests/scripts/test_herdr_worktree_watch.py` (new in `6d3e125a`: remove)
- `tests/scripts/test_detach.py` (new in `2d7b96f0`: remove)
- `tests/scripts/test_capture_scripts.py` (new: remove)

Separately, revert the Phase 1 edits in `docs/plans/coder-worktree-fixes/acceptance-criteria.md`, `docs/plans/coder-worktree-fixes/plan.md`, `docs/changes/changelog.md` and `docs/changes/index.md`.
