---
type: "Change"
change_type: "fixed"
title: "A restored herdr lane resumes with the cron scheduler off"
description: "A herdr shell whose folder is a registered lane worktree exports CLAUDE_CODE_DISABLE_CRON=1, so a lane that herdr restores after a restart no longer fires the orchestrator's cron jobs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T16:23:27-06:00"}
seq: 2
kind: "fix"
components: ["script/lane-env", "shared/lane-entries"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_lane_env.py::LaneEnvTest::test_lane_worktree_in_herdr_disables_cron"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; no intake number counts timer fires in restored lanes."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `scripts/.local/lib/lane-env.zsh`, sourced by `zsh/.zshrc`. In a herdr pane (`HERDR_ENV=1`), it reads the lane file named after the folder, `<state>/herdr-lanes/<folder>.json`, where `<state>` is `$XDG_STATE_HOME` when it is an absolute path and `~/.local/state` otherwise (the rule `script_utils.xdg_state_home` uses). When that file's `worktree` line names the current folder, it exports `CLAUDE_CODE_DISABLE_CRON=1`. It starts no process, so every herdr shell start pays one file read at most. It escapes a backslash or double quote in the folder path the way JSON does before the match, and `lane_entries.py` now writes lane files as UTF-8 with non-ASCII characters unescaped, so a non-ASCII path matches too. It compares the symlink-resolved folder (`${PWD:A}`), and `lane_entries.py` refuses a lane field with a non-UTF-8 byte at write, because herdr-lane-resume reads lane fields through jq, which cannot carry it.

## Evidence

judgment: herdr 0.8.2 restores an agent pane in `src/app/agent_resume.rs` `start_pending_agent_resume`. It spawns a fresh default shell in the saved folder, with only herdr's pane identity variables (`pane_launch_env` with an empty extra list, `src/app/ids.rs`). Then it types `'claude' '--resume' '<id>'`. The inline variable that `herdr-dev` typed is lost, and the resume argv is fixed in herdr, so the shell the restore spawns has to supply the variable.

## Result

All 13 tests in `tests/scripts/test_lane_env.py` pass, and the lane-worktree case fails without the file. On a real lane file, a herdr shell in that lane prints the variable set.

## Watch

None: no intake number reads it.

## Back-out

Remove the `lane-env.zsh` source line from `zsh/.zshrc`.
