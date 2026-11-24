---
type: "Change"
change_type: "changed"
title: "A fork replaces a stale lane entry, the review pane labels itself through herdr-api, and one owner lists the agents in a folder"
description: "A fork of a label whose old lane entry has no live worktree gets its own brief and report-to session; the review pane is labelled under tuios too; herdr-lane-resume asks session_pane.py which agents run in a folder instead of a second bash check."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T21:46:54-06:00"}
seq: 38
kind: "fix"
components: ["script/herdr-worktree", "script/herdr-worktree-watch", "script/herdr-lane-resume", "script/hunk-review-pane", "script/session-pane", "script/lanes", "script/pull-keep-index"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrWorktreeTest::test_a_fork_replaces_a_stale_entry_of_the_same_label_with_no_live_worktree"
asked: ""
proof: []
unmeasured: ""
---

## Change

The branch-wide review of fix/herdr-tools-nov22 found eight things; this note carries all of them.

- `herdr-worktree --fork` removes any lane entry named for the new label before `git worktree add`. Before, `lanes.py add` saw the new folder as the old entry's live worktree and refused, so the old brief and report-to session stayed and `herdr-lane-resume` sent them to the new fork.
- `hunk-review-pane` labels its pane through `herdr-api pane rename`, which reaches the tuios shim when `TUIOS_SOCKET` is set. Bare `herdr pane rename` failed silently under tuios and `nvim-jump` found no `review` pane.
- `session_pane.py agents-in FOLDER [KIND]` prints the agents running in a folder as JSON; `herdr-lane-resume` calls it in place of its own bash copy, which disagreed with `lib/herdr_agents.py` on a folder that no longer exists.
- `herdr-worktree-watch` logs the lanes stderr when a lookup fails, in place of "lane file unreadable", and looks the entry up once per pass.
- `lanes.py path NAME` prints the lane file path; `herdr-worktree` uses it instead of building the path in bash.
- `calibration_guard.py` reads the XDG state home through `script_utils.xdg_state_home`.
- `pull_keep_index.run_page_driver` fills `%L` with git's default conflict-marker size, 7.

## Evidence

New tests: the fork-after-stale-entry test named above; `SessionPaneAgentsInTest` (4 tests) in `tests/scripts/test_session_pane.py`; `test_the_page_driver_gets_gits_default_conflict_marker_size_for_percent_l` in `tests/scripts/test_pull_keep_index.py`; `test_path_prints_the_lane_file_of_a_name_with_no_entry_and_refuses_a_bad_name` in `tests/scripts/test_lanes.py`. The watcher and hunk-review-pane tests were updated to the new log line and the `herdr-api` stub. 9 test files, 241 tests, 0 failed.

## Result

See Evidence.

## Watch

No intake number reads these scripts.

## Back-out

Revert the commit.
