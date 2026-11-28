---
type: "Change"
change_type: "added"
title: "land_lane lands a dotfiles lane on the first run"
description: "tools/land_lane.py lands a lane in one command: it stops before any push when the main checkout holds changes to the lane's files, merges origin/master when the lane is behind, runs the suite unless a green suite receipt covers the tree, pushes HEAD:master and pulls into the main checkout."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T09:26:16-06:00"}
seq: 1
kind: "fix"
components: ["script/land-lane", "script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_land_lane.py::LandLaneTest::test_origin_ahead_lands_in_one_run"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `claude/.claude/scripts/tools/land_lane.py <lane worktree> [--main ~/dotfiles] [--base master] [--remote origin]`.
It stops when the main checkout does not have the base branch checked out. It fetches, then lists the files the
lane's commits touch and stops when the main checkout holds any of them staged or unstaged, naming each file and the
way out. It merges `origin/master` into the lane when behind; a conflict aborts and
names the files. The suite runs unless a green `suite_receipt.py check` covers HEAD's tree. It checks the main
checkout again and stops when the lane is dirty or its commit or branch moved since the merge, then pushes the commit
the suite vouched for (up to three tries on a non-fast-forward) and runs `pull_keep_index.py` on the main checkout.
There is no suite override: the suite is the lane's own `tests/run.sh`. A corrupt receipt row stops with a repair hint;
a git failure while reading receipts stops with the inspect hint. The `rerun:` line uses the resolved paths.
`pull_keep_index.py` is unchanged. Status lines come from `worktree_snapshot.status_entries`.

Only the user runs it: `git_discipline_gate.py` rule 11 denies a session's Bash call that runs `land_lane.py`
(`lib/land_lane_calls.py` reads the command through the shell parsing owners), since its push happens inside Python
where rule 7 cannot see it. Tests: `LandLaneGateTest` in `tests/scripts/test_git_discipline_gate.py`.

## Evidence

The landing line `git push origin HEAD:master && pull_keep_index.py ~/dotfiles` failed when master had moved
(non-fast-forward), and three merge lines in one night stopped on another session's staged or unstaged files in the
main checkout. Each failure cost the user a rerun.

## Result

Before: no tool did these steps; the line failed mid-way. After: 30 tests in `tests/scripts/test_land_lane.py` pass.
`test_origin_ahead_lands_in_one_run` lands with origin one commit ahead, and
`test_main_changes_to_lane_files_stop_before_the_push` names a staged deletion and a dirty file and pushes nothing.
`test_merge_leaving_the_tree_unchanged_runs_the_suite_without_a_receipt` and
`test_unreadable_suite_receipt_stops_before_the_push` failed before the last fix pass and pass after.

## Watch

None: no intake number counts landing reruns. Read the next landing lines for a rerun.

## Back-out

Delete `tools/land_lane.py`, `tests/scripts/test_land_lane.py`, its `toolkit_paths.py` entry and its owner line in
`claude/.claude/scripts/CLAUDE.md`.
