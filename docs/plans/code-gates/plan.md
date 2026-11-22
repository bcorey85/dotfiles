# Code gates: /code run's start, resume, hand-back and commit gates

Fix four queued toolkit defects in the gates around a `/code` run. Each phase starts with a test that fails on the
current tree. Scripts live in `claude/.claude/scripts/` (paths below are relative to it unless they start with
`claude/`, `scripts/` or `tests/`); tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`. Follow
`docs/toolkit-script-rules.md` and `claude/.claude/scripts/CLAUDE.md` (owners, no second copy of a fact).

## Scope

- In: `lib/check_output.py`, `gates/quality_check_cap.py`, `lib/shell_statements.py`, `review/review_commit_gate.py`
  and a new module split out of it, `code/coder_gate.py`, `code/code_relay.py`, `code/phase_start.py`, a new
  `lib/code_stop_record.py`, their tests. No prompt file changes.
- Out: `review_loop*`, `review_fix*`, `verify*` (the review-asks lane).
- Dropped in triage: interpreter-inline-hook-blocks-python-m-module (the CB generator owns it);
  stale-code-phase-start-record-from-an-earlier-run (already fixed by 7caa63e3 and 9d210139, with tests);
  commit-gate-ignores-converged-review-from-code (the credit path exists through `review_loop_packet` →
  `handback.record_clean_review`; one sighting that self-recovered).

## Phase Status

- [x] Phase 1: the quality-check cap does not count a run that a shell parse error stopped before it started (risk: low)
- [x] Phase 2: the commit gate passes session-scratch repos and commit words quoted in a piped script's arguments (risk: medium)
- [x] Phase 3: the hand-back gate runs in the checkout `coder_gate.py set` ran in, not the hook's cwd (risk: medium)
- [x] Phase 4: `/code resume` resolves the run from the named path or this session's last stop (risk: medium)

## Phase 1: shell parse errors do not count toward the quality-check cap

Bug: a check command with a quoting slip (`(eval):1: unmatched "`, `zsh:1: parse error near ...`) fails before any
step runs. `gates/quality_check_cap.py`'s PostToolUseFailure branch records it as a failed run, so the clean rerun
after the fix is capped.

Fix:

- `lib/check_output.py`: add `shell_parse_error_line(output)`: the first line of the output, after one optional
  `Exit code N` line, when it is a shell's parse error: prefix `(eval):N: `, `zsh:1: `, `bash: line 1: ` or
  `bash: -c: line 1: ` (a script runs line by line, so a later line means earlier lines ran), then
  `unmatched "`, `unmatched '`, `` unmatched ` ``, `parse error near`, `parse error`, `unexpected EOF` or
  `syntax error near unexpected token`. None otherwise. `no matches found` and `bad substitution`
  are runtime errors: the steps before them ran. The `[[` form of `condition expected` is already a `parse error`.
- `gates/quality_check_cap.py`: the failure skip block also skips when `shell_parse_error_line(error_text)` is set.

Tests: `test_check_output.py`: each real shape (`(eval):1: unmatched "` bare and after `Exit code 1`, `(eval):1:
unmatched '`, `zsh:1: parse error near `)'`) is found; `no matches found` and a runner's own `SyntaxError` are not. A parse-error text on line 2 or later (`bash: line 2: ...`,
or a parse error after other output) returns None.
`test_quality_check_cap.py`: a failed run whose error is `Exit code 1\n(eval):1: unmatched "` then a clean rerun of the
same command is allowed and not counted.

**File**: `claude/.claude/scripts/lib/check_output.py`, `claude/.claude/scripts/gates/quality_check_cap.py`
**Test**: `tests/scripts/test_check_output.py`, `tests/scripts/test_quality_check_cap.py`

## Phase 2: the commit gate passes session-scratch repos and quoted commit words

Bug 1: a session saves a throwaway repo under its own scratchpad (`git -C <scratchpad>/plantrepo -c user.name=b -c
user.email=b@b commit -qm base`). Any "dirty" event marks every repo dirty, so the gate denies the commit.

Bug 2: `shell_statements.blank_script_run_quotes` leaves a script step that a `|` follows as written. So
`python3 bin/build_queue.py new --body $'... git -C d commit ...' 2>&1 | tail -5` reads as a commit and is denied.

Fix:

- `review/review_commit_gate.py` is 1036 lines. First move the dirty tracking (`gate_events`, `subagent_transcript`,
  `worked_until`, `folder_repo_top`, `edited_repos`, `edited_dirs_in`, `edited_repos_by_agent`, `dirty_since`) into a
  new `review/commit_gate_dirty.py` with no behavior change; the gate imports it. The gate then stays under 1000 lines.
- In `commit_gate_dirty.py`: `is_session_scratch_repo(repo_top, session, edited, events)`: True only when the work
  tree and its git common dir both lie under `<root>/<project slug>/<session>/` for a root in
  `hook_input.session_temp_roots()`, no coder dispatch's edited repos name it, no coder's edits are unreadable and no
  dispatch lacks an agent id (fail closed). `is_clear` returns True for such a repo, unless it is
  `latest_reviewed_repo(session)`.
- `lib/shell_statements.py` `blank_script_run_quotes`: a script step that a `|` follows is blanked when no later step
  of that pipeline (up to the next operator that is not `|`) names a code runner (`shell_command.names_code_runner`).
  `| fish`, `| nu`, `|&` and process substitution stay as written (existing tests).

Tests: `test_review_commit_gate.py`: a captured `git -C <scratchpad>/x -c ... commit` event with a dirty event in state
passes; the same commit in a repo outside the scratchpad is still denied; a scratch repo a coder dispatch edited is
still denied. The captured build_queue command (with `2>&1 | tail -5`) is not a commit. `test_shell_statements.py`: a
script step piped into `tail -5` is blanked; one piped into `tail | sh` stays as written.

**File**: `claude/.claude/scripts/review/review_commit_gate.py`, `claude/.claude/scripts/review/commit_gate_dirty.py`, `claude/.claude/scripts/lib/shell_statements.py`
**Test**: `tests/scripts/test_review_commit_gate.py`, `tests/scripts/test_shell_statements.py`

## Phase 3: the hand-back gate runs in the checkout the run set it in

Bug: `coder_gate.run_hook` finds the gate file from the hook event's `cwd`. When the session's cwd is another checkout
(a sibling worktree), the gate reads that checkout's gate file, or none, and a failure there blocks or skips the
wrong run.

Fix:

- `code/coder_gate.py set`: also write a session pointer through `script_utils.state_file_path`, keyed by
  `CLAUDE_CODE_SESSION_ID`, holding only the absolute gate file path, in one atomic write. With no
  session id, write no pointer.
- `run_hook`: read the event's `session_id`. When a pointer for the session exists, use its gate file (none left:
  allow, run nothing); else the cwd as today.
- `clear`: remove the pointer when it names this gate file.

Tests: `test_coder_gate.py`: set in repo A with a session id, then a hook event with `cwd` in repo B and that session
id runs A's commands in A; B's failing gate is not run. No pointer: the cwd's gate runs. After `clear`, the pointer is
gone.

**File**: `claude/.claude/scripts/code/coder_gate.py`
**Test**: `tests/scripts/test_coder_gate.py`

## Phase 4: `/code resume` resolves the run by path or by this session's last stop

Bug: resume reads the run folder of the cwd's repo. A session whose cwd moved to another checkout resumes the wrong
run, or finds none. A run with no plan file prints `To go on: /code resume <your feedback>`, which names no path.

Fix (scripts only; no SKILL.md edit, per the orchestrator's ruling):

- New `lib/code_stop_record.py`: `record_stop(session, run_folder, repo_top, go_on)` and `last_stop(session)`, one
  state file per session through `script_utils.state_file_path`, holding the run folder, its repo top, the relayed
  `To go on:` line and the time; one atomic write. The repo top is a third argument because the run folder is `<git dir>/code-phase`, which does not
  give the repo top.
- `code/code_relay.py` (the main session runs it after every /code hand-back): when it relays a `stop.md` stop, record
  it with `CLAUDE_CODE_SESSION_ID` (no id: no record). When that stop's `To go on: /code resume ...` line holds no
  absolute path, insert the run's repo top right after `resume`, so the resume line always names where the run
  lives. A line that already names an absolute path stays as written.
- `code/phase_start.py --resume`: before stop.md is moved aside, when this repo's run folder holds no `stop.md` and
  no `stop.prev.md` newer than the recorded stop's time, and this session's last stop names another run folder, exit
  non-zero naming both run folders and the recorded `To go on:` line (`/code resume <repo top>` for a finished stop).
  A repo whose run folder holds its own newer stop resumes as today.

Tests: `test_code_relay.py`: a relayed stop is recorded for the session; a `To go on: /code resume <your feedback>`
line gets the repo top; a line with the plan path stays as written. `test_phase_start.py`: `--resume` in repo B with
no stop there and a recorded stop in repo A exits non-zero naming both; `--resume` in a repo with its own stop.md
goes on; no session id or no record goes on.

**File**: `claude/.claude/scripts/lib/code_stop_record.py`, `claude/.claude/scripts/code/code_relay.py`, `claude/.claude/scripts/code/phase_start.py`
**Test**: `tests/scripts/test_code_relay.py`, `tests/scripts/test_phase_start.py`

## Plan Deviations

- Phase 4 ruling (agent-evals-5e, 2026-11-21): no SKILL.md edit, since a reworded step needs rule-meter arms; the
  resume check goes in scripts the run already calls (`code_relay.py`, `phase_start.py --resume`).
- Phase 2: AC2 holds as written; user.name=/user.email= added to DIRECTORY_FREE_CONFIG so the captured form is placed (orchestrator, 2026-11-21).
- Phase 1 AC1 reword ruling (agent-evals-5e orchestrating session, 2026-11-21): "before the gate starts" -> "before any step of the command runs"; session ruling, criteria owner is plan, no ticket.
- Phase 1 full check ruling (agent-evals-5e, 2026-11-21): test_rule_anchors fails on master already and is out of scope; the full check counts as passing with that one known pre-existing failure.
- Phase 4: record_stop takes repo_top as a third argument; no criterion changed (adopted, 2026-11-21).
- Phase 2 ruling (orchestrating session, 2026-11-21): review ask "add `| grep .` handling" rejected: it fails safe and no session hit it, so per the toolkit size rule it gets no code.
- Phase 2 ruling (orchestrating session, 2026-11-21): DIRECTORY_FREE_CONFIG added, accepted by the orchestrating session. test_rule_anchors is the known master failure, out of scope, as in Phase 1.
- Phases 3 and 4 ruling (orchestrating session, 2026-11-21), standing for the rest of this branch: the test_rule_anchors failure is the known master failure and stays out of scope for every remaining phase of this branch, Phases 3 and 4 included.
- Phase 3 ruling (orchestrating session, 2026-11-21): a pointer naming a missing gate file means allow (AC5 reading).
- Phase 3 ruling (orchestrating session, 2026-11-21): the pointer drops repoRoot; the plan lines are reworded.
- ruling (orchestrating session, 2026-11-21): AC6 narrowed — the refusal covers the phase_start.py --resume path only; SKILL.md:32 sends a no-path resume with no stop.md to step 0, which the repo top in the relayed To-go-on line (AC7) covers. Also: the Phase 4 full check counts as passing; its one failure, test_rule_anchors, is the known master failure covered by the Phases 3 and 4 ruling already logged.
- Phase 4 ruling (orchestrating session, 2026-11-21): the no-SKILL.md ruling stands; a repo folder after `resume` names the repo whose run folder holds the run, which the resume rule already reads as the repo root, so no change.
- Phase 4 ruling (orchestrating session, 2026-11-21): AC6 and the resume refusal reworded: skipped only with a stop.md, or a stop.prev.md newer than the recorded stop; the refusal prints the relayed `To go on:` line.
- Phase 4 ruling (orchestrating session, 2026-11-21): no `--named-path` flag; a repo holding its own newer stop resumes under the AC6 rule, and no session hit the named-path case.
- Branch review ruling (orchestrating session, 2026-11-21): one /code run per session is the supported model for the coder-gate pointer; the stale-pointer reach is documented, no per-repo pointer. A scratch repo with a remote is not exempt from the commit gate. A pipe into an expansion (`| $SHELL`) counts as a code runner. No criterion changed.
