---
type: "Change"
change_type: "added"
title: "herdr-lane-resume reopens a dead lane from its lane file and closes finished ones"
description: "A lane whose herdr workspace died restarts in one command from its lane file, and a finished lane is closed and its merged worktrees pruned in another."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T19:28:07-06:00"}
seq: 30
kind: "fix"
components: ["script/herdr-lane-resume", "script/herdr-dev"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_herdr_lane_resume.py::ResumeTest::test_resume_opens_the_workspace_and_runs_herdr_dev_resume"
asked: ""
proof: []
unmeasured: "No count shows how often a dead lane was reopened by hand."
---

## Change

`herdr-lane-resume <name>` reads the lane file entry written by `herdr-worktree --fork`, stops with a reason when the worktree is gone, the fork never reported a session id, an agent of any kind already runs in the worktree, or a workspace is already open on it. Otherwise it reopens the workspace (`herdr worktree open`, or `workspace create` under tuios) and starts `herdr-dev --resume` there.

`herdr-lane-resume --close <name>` refuses when a claude agent in the worktree is working, closes the lane's workspaces, waits up to `HERDR_LANE_CLOSE_WAIT` seconds (default 10) for the agents to leave, removes the lane entry and runs `herdr-worktree-prune --apply` in the main checkout. Every failed read of the lane file or the herdr API stops with its own message.

`herdr-dev --resume` runs `claude --resume <session> --name <name>` in the new pane, without `--fork-session`; the positional fork mode is unchanged.

## Evidence

The tests run both scripts against stub herdr, herdr-api, herdr-dev and prune commands and the real lanes.py. They cover the resume path, five resume stops, each close case, tuios label matching, symlinked paths, sibling folders with a shared prefix, null fields in the lists, unexpected list shapes and a failing poll after the close.

## Result

The herdr-lane-resume tests pass (32), the herdr-dev tests pass (3), lint passes, and the full check passed in the review loop. The manual live-lane check has not run.

## Watch

The tuios shim's `workspace list` shape, which is unchecked here.

## Back-out

Delete `herdr-lane-resume` and its tests, and revert `herdr-dev` and its tests to the version without `--resume`.
