---
type: "Change"
change_type: "changed"
title: "A brief alone starts a lane: herdr-worktree no longer forks the orchestrator by default"
description: "herdr-worktree --prompt-file <brief> <branch> opens a headless lane with a fresh claude session on the brief; --fork stays as the opt-in that also resumes the caller's conversation."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-27T12:00:00-06:00"}
seq: 1
kind: "user-rule"
components: ["script/herdr-worktree", "script/herdr-dev", "rule/orchestration", "script/herdr-worktree-watch", "script/herdr-lane-sweep", "shared/lane-brief"]
evidence: ["rule meter", "tests"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrWorktreeTest::test_a_brief_without_fork_opens_a_headless_lane_on_an_empty_session_id_with_entry_and_watcher"
asked: "2026-11-27: the user asked for the forked-lane issue to be fixed"
proof: []
unmeasured: "Tokens and compactions of a fresh lane against a forked one: the bench pair the orchestrator runs after the branch lands."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `scripts/.local/bin/herdr-worktree`: a run with `--prompt` or `--prompt-file` is a lane. Helper and timeout checks,
  base HEAD, stale-entry removal, the lane entry, `--headless`, the agent wait and the watcher key on the lane, not on
  `--fork`. Only `--fork` reads the caller's claude session; a fresh lane passes an empty session id. `--fork`
  without a brief still fails. An empty brief, from `--prompt` or `--prompt-file`, exits 1 with `the brief is empty`
  (naming the file for `--prompt-file`).
- `scripts/.local/bin/herdr-dev`: with no `claude_session` and a `start_prompt`, the claude pane runs
  `CLAUDE_CODE_DISABLE_CRON=1 claude --name <worktree folder> -- "$(cat '<file>')" && rm -f '<file>'`, with no
  `--resume`. With neither it stays plain `claude`.
- `claude/.claude/orchestration.md` lane-start line and `claude/.claude/skills/_shared/lane-brief.md` opening line name
  the fresh form. `herdr-worktree-watch` says "the lane's session id", and its comments and the `herdr-lane-sweep` usage text no longer name `--fork` as the lane start.
- Tests: `test_herdr_worktree.py` (fresh lane run, the pane that never shows claude, the empty brief file and empty `--prompt`, base HEAD and stale-entry
  replacement with and without `--fork`, herdr-dev fresh command and plain claude),
  `test_lane_brief.py` (the rule text).

## Evidence

A forked lane carries the orchestrator's whole history and compacts before any work.

## Result

`test_a_brief_without_fork_opens_a_headless_lane_on_an_empty_session_id_with_entry_and_watcher` and `test_a_prompt_with_no_session_starts_a_fresh_named_claude_with_no_resume` fail against the base scripts and pass after. `test_no_session_and_no_prompt_types_plain_claude` guards behavior that was already there.

Rule meter, sonnet, 3 runs per cell, detector `lane_start_is_fresh` (COMPLIED is a lane command with no `--fork`). WR05 holds the new lane-start clause; WRB5 holds master's `--fork` clause. The off arm deletes the clause.

| Scenario | Level | On | Off |
|---|---|---|---|
| WR05 (new) | supportive | 3/3 | 3/3 |
| WR05 (new) | neutral | 3/3 | 3/3 |
| WR05 (new) | competing | 0/3 | 0/3 |
| WRB5 (old) | supportive | 1/3 | 3/3 |
| WRB5 (old) | neutral | 0/3 | 0/3 |
| WRB5 (old) | competing | 0/3 | 0/3 |

New line on 6/9 against old line on 1/9 fresh starts. The new clause alone moves nothing against its own off arm: the task quotes the new `--help` text. The competing level asks that the lane know the whole conversation, and every arm then forks. The script default does the work; the orchestration line is navigation only.

## Watch

None.

## Back-out

Revert the commit; a lane then starts only with `--fork`.
