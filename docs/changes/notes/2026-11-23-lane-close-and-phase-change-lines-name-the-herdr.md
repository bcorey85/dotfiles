---
type: "Change"
change_type: "changed"
title: "Lane close and phase-change lines name the herdr lane scripts"
description: "The orchestration Git section now tells the orchestrator to close a merged lane with herdr-lane-resume --close, and says herdr-phase-change takes the worker's ListAgents name and adds the report-to line itself; the dotfiles CLAUDE.md lists the two new lane scripts and where shared script defaults live."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T00:48:22-06:00"}
seq: 1
kind: "user-rule"
components: ["rule/orchestration"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-23: the user approved writing the documentation lines for the new herdr lane scripts"
proof: []
unmeasured: "No rule-meter fixture runs herdr: closing a lane and moving a worker to its next phase need a live herdr server and a forked lane, which the meter's headless arms do not have. The user approved the wording before it ships."
---

## Change

- `claude/.claude/orchestration.md`, Git section:
  - The phase-change line says `<agent>` is the worker's ListAgents name and that the script adds the report-to
    line naming the calling session. Before, an orchestrator added its own report-to text or passed a pane id.
  - New line: once a lane's branch is merged, close it with `herdr-lane-resume --close <name>`, which closes the
    workspace, removes the worktree and drops the lane file entry. Before, the orchestrator ran three separate
    commands (herdr worktree remove, git worktree prune, branch delete) and left lane file entries behind.
- `CLAUDE.md` (dotfiles, not toolkit): the scripts package line names `herdr-lane-resume` and `lane-status`; Key
  Conventions says a path or env-var default two scripts share lives in a sourced file under `scripts/.local/lib`.

## Evidence

- user request: the user approved the lines after the herdr lane tools landed on master.

## Result

Written. No meter run: see `unmeasured`.

## Watch

None: see `unmeasured`.

## Back-out

Revert the two lines in `orchestration.md` and the two lines in `CLAUDE.md`.
