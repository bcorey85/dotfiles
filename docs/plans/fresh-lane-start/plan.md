# Fresh lane start: a lane starts from its brief, not a fork of the orchestrator

`herdr-worktree --fork` resumes the calling conversation in the new pane, so a lane carries the orchestrator's whole
history and compacts before any work. Make a brief alone start a lane: `herdr-worktree --prompt-file <brief> <branch>`
(no `--fork`) opens the same headless lane as `--fork` today, with a fresh claude session whose first prompt is the
brief. `--fork` stays as the opt-in that also resumes the parent conversation.

## Scope

- In: `scripts/.local/bin/herdr-worktree`, `scripts/.local/bin/herdr-dev`, the comments that name `--fork` as the lane
  start in `herdr-worktree-watch`, `herdr-lane-sweep`; `claude/.claude/orchestration.md` lane-start line;
  `claude/.claude/skills/_shared/lane-brief.md` opening line; the tests of each script.
- Out: `herdr-lane-resume`, `land_lane.py`, every CLAUDE.md (lines that must change go to agent-evals-c3-owner).

## Phase Status

- [ ] Phase 1: a brief without --fork starts a fresh headless lane (risk: medium)

## Phase 1: a brief without --fork starts a fresh headless lane

1. `herdr-dev`: with no `claude_session` and a `start_prompt`, the claude pane runs
   `$lane_claude --name <worktree folder> -- "$(cat '<file>')" && rm -f '<file>'`: cron off, named for the worktree,
   no `--resume`. With no session and no prompt it stays plain `claude`. Update the usage text.
2. `herdr-worktree`: a run with `--prompt` or `--prompt-file` is a lane. Every step now gated on `--fork` that a lane
   needs (helper check, watch and timeout checks, base defaults to HEAD, stale entry removal, lane entry, `--headless`,
   the agent wait and the watcher) is gated on the lane. Only `--fork` reads the caller's claude session and passes it
   to herdr-dev and the watcher; a fresh lane passes an empty session id. `--fork` without a brief still fails. Update
   the usage text.
3. `orchestration.md:35` lane-start line: run `herdr-worktree --prompt-file <brief file> <branch>`; the new pane starts
   a fresh session on the brief. Rule-meter on and off arms for the reworded line; counts in the change file.
4. `lane-brief.md:3`: a lane is a session started in its own worktree by `herdr-worktree` from its brief.

#### Automated Verification

New tests in `tests/scripts/test_herdr_worktree.py`: a run with a brief and no fork flag passes herdr-dev
`--headless` and an empty session id with the brief, writes the lane entry and starts the watcher; herdr-dev with an
empty session id and a prompt types a command with no resume flag, starting with
`CLAUDE_CODE_DISABLE_CRON=1 claude --name <folder> -- `.

- [ ] **Script tests**: the three herdr script test files pass - `python3 tests/parallel_tests.py test_herdr_worktree.py test_herdr_dev.py test_herdr_worktree_watch.py`
- [ ] **Full suite**: every test passes - `bash tests/run.sh`

## Plan Deviations
