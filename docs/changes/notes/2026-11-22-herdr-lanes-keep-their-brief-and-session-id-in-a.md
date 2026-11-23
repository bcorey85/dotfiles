---
type: "Change"
change_type: "fixed"
title: "herdr lanes keep their brief and session id in a durable lane file"
description: "A herdr-worktree fork writes its lane file at once, the watcher stores the fork's session id in it, and herdr-phase-change keeps the id and the sent prompt current."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T17:11:52-06:00"}
seq: 23
kind: "fix"
components: ["script/herdr-worktree", "script/herdr-worktree-watch", "script/herdr-phase-change", "script/session-pane"]
evidence: ["tests", "review rounds", "probe lane"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrWorktreeTest::test_a_fork_writes_a_lane_entry_with_the_brief_worktree_branch_and_sender_before_the_session_id_is_known"
asked: ""
proof: []
unmeasured: "No intake number counts lanes recovered from the file yet: a later phase reads the entry on resume."
---

## Change

- `herdr-worktree --fork` writes the lane file (brief, worktree, branch, sender in `reports_to`) before the fork
  starts. A write that fails warns with the file and the fork still starts. A run without `--fork` writes nothing.
- `herdr-worktree-watch` stores the fork's session id in the entry of its own worktree. When the workspace is gone
  and an id is stored, the log gives the lane resume step only. An entry for another worktree with the same name, or
  with no readable session id, leaves the manual recovery steps in place.
- `herdr-phase-change` stores the new session id and the sent prompt in the lane of the agent's worktree. An agent
  outside every lane, or one that reports no cwd, writes nothing. A failed lane update warns and still exits 0 after
  the prompt went out.
- New `tools/session_pane.py` names the session of a pane for these scripts.

## Evidence

- `python3 tests/parallel_tests.py` on `test_herdr_worktree.py`, `test_herdr_worktree_watch.py`,
  `test_herdr_phase_change.py` and `test_session_pane.py`: all pass. `bash tests/lint.sh` on `session_pane.py`: pass.
- Probe lane: a no-op fork from a scratch clone, then `lanes.py get <name>` showed the brief and a non-empty
  `session_id` filled in by the watcher.
- Review converged; the full check passed.

## Result

Applied. A forked lane has its lane file with the brief and session id before the user touches anything.

## Watch

None: see `unmeasured`.

## Back-out

Revert the commit.
