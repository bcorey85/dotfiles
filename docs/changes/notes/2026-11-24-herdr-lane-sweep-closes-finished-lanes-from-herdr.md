---
type: "Change"
change_type: "added"
title: "herdr-lane-sweep closes finished lanes from herdr-worktree and the wake timer"
description: "A new herdr-lane-sweep closes every lane whose branch is merged, runs at the start of each herdr-worktree run and at most every 10 minutes from herdr-wake-limited, and keeps any lane with unmerged commits, a dirty tree, a working claude pane or the caller inside it."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T15:22:41-06:00"}
seq: 1
kind: "user-rule"
components: ["script/herdr-lane-sweep", "script/herdr-worktree", "script/herdr-wake-limited", "script/lanes"]
evidence: ["user report"]
watches: []
test: ""
asked: "2026-11-24: asked by the user"
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- New `scripts/.local/bin/herdr-lane-sweep` reads the lane list and closes each finished lane through `herdr-lane-resume --close`.
  - A lane is finished when its branch has a commit past the recorded `base_commit`, and its tip is in origin's default branch or in origin's copy of the main checkout's current branch.
  - It keeps a lane with a dirty tree, unmerged commits, no recorded base, no commit since its base, the caller's current folder inside it, a working claude pane, or one not decided by the 60 s deadline.
  - It prints `closed <name>` or `kept <name>: <reason>` per lane.
- `herdr-worktree` runs the sweep after its checks, before any workspace is made. A failed sweep only warns. `--fork` records `base_commit` through the new `lanes.py add --base-commit`, an optional field in `lane_entries.py`.
- `herdr-wake-limited` runs the sweep at most once per 10 minutes, logs to a file beside its stamp, waits up to 300 s and then kills the sweep's process group. A sweep failure never changes its output or exit code.
- Shared helpers in `scripts/.local/lib`: `lane_list.py`, `quiet_git.py` and `first_output_line.py`. `herdr-worktree-prune` now uses the first two.
- Not in this change: the scripts list and `install/herdr-wake-limited` lines in the repo CLAUDE.md, and the close rule at `claude/.claude/orchestration.md:37`. The orchestrating session routes both after the branch lands.

## Evidence

user report: orchestrators leave finished lane workspaces open, with claude and hunk panes that hold memory, and the user closes them by hand.

## Result

The full test suite and lint pass on the branch. The tests cover each close and keep path with temp git repos and a stubbed herdr.

## Watch

—

## Back-out

Remove the sweep line from `herdr-worktree` and the sweep call from `herdr-wake-limited`. Lanes then stay open until closed by hand with `herdr-lane-resume --close`.
