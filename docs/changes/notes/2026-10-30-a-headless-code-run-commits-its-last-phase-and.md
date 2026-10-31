---
type: "Change"
change_type: "fixed"
title: "a headless /code run commits its last phase and hands back"
description: "A headless /code run ends with its last phase committed and its report, so the orchestrator no longer sends a go-ahead message each time a run stops to have a person stage files."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T05:48:36-05:00"}
seq: 326
kind: "fix"
components: ["script/code-step", "script/worktree-snapshot", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_headless_run_commits_its_last_phase_by_path_and_hands_back_with_no_wait_to_stage"
asked: ""
proof: []
unmeasured: ""
---

## Change

- In a run started with `--headless`, block C (the last phase the run can do: `--phase N`, a gated phase ahead, or
  no open phase left) now prints the new action `commit-and-hand-back` in place of `stop-block-C`. The session runs
  the phase's commit command and hands back. If the commit is refused, the session hands back with the refusal and
  does not retry. Without `--headless`, block C stays as it was.
- The headless block names the files it commits in place of the `/stage` queue. No headless step tells the session
  to wait for a person to stage.
- A gated phase ahead still ends the run. The commit only happens at the stop.
- The commit command adds and commits the phase's files by path, as before. The commit text now names any file
  that was already staged outside the phase and stays staged and uncommitted. This applies to every phase-end
  commit, not just headless ones.
- The `/code` skill gets one line for the new action.

## Evidence

judgment: a headless `/code` worker finished Phase 1 with a converged review. It then stopped with its files
unstaged and told its orchestrator it was waiting for the user to stage them. The orchestrator had to send the
go-ahead by message. The earlier headless fix covered only block B.

## Result

The named test fails before (the run prints `stop-block-C` and the `/stage` queue) and passes after.
`test_a_headless_run_stops_before_a_gated_phase_after_committing_the_phase_before_it` pins the stop before a gated
phase. `test_a_headless_last_phase_commit_leaves_a_file_staged_by_hand_staged_and_names_it` pins that a file staged
by hand stays staged. `test_a_headless_last_phase_commit_message_is_one_subject_line_with_no_attribution` pins the
message: one subject line and no attribution line.

## Watch

None.

## Back-out

In `code_step_boundary.py`, delete `announce_headless_run_end` and the branch in `announce_boundary` that calls it,
plus the staged-by-hand note in `phase_commit` and `worktree_snapshot.staged_paths`. In `code_step_phase_end.py`,
delete the `committed_files` parameter. Revert the `--headless` usage line in `code_step_start.py`. Remove the skill
line, the termination-test entry and the four tests.
