# Review/code batch 5: loop coders may delete their own untracked files, ruff through pre-commit, stale stop files

Fix three queued toolkit defects. Each phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

## Scope

- In: `review/review_loop_coder.py` (and its caller in `review/review_loop_script.py` only if the call needs a new
  argument), `lib/format_files.py`, `code/phase_start.py`, `lib/stop_file_names.py`, their tests, and one change note
  per fix in `docs/changes/notes/`.
- Out: prompt files under `claude/.claude/agents/` and `claude/.claude/skills/` (a prompt rule needs rule-meter runs),
  and `claude/.claude/scripts/gates/` (another lane owns it). Dropped in triage: the class-closure autocompact item
  (the closure prompt already names diff paths, not contents; one sighting, a resume recovered) and the lost
  SubagentHandback item (the refusal is Claude Code's own tool, not a toolkit hook).

## Phase Status

- [x] Phase 1: a loop coder may delete an untracked file an earlier coder of the same loop wrote (risk: medium)
- [x] Phase 2: format_files reads ruff and ruff-format from a pre-commit-only repo (risk: low)
- [x] Phase 3: phase_start moves a stale stop.md aside (risk: low)

## Phase 1: a loop coder may delete an untracked file an earlier coder of the same loop wrote

Bug: `review_loop_coder.coder_call` backs up every untracked file that is not held, and `put_back_untracked`
restores each one a coder deleted, as a tool fault. A file an earlier coder call of the same loop created (a stale
duplicate it left behind) is restored too, so a later coder can never remove it, the type check stays red and the
loop ends deferred.

Change: record, per coder call, the untracked files that are present after the call and were not present before it
(the files that call wrote). Keep that record for the whole loop run (module state next to `UNTRACKED_FAULTS`, or
state the loop passes in; pick what fits the module). A later coder call does not back up and does not restore a
recorded file; its deletion is no tool fault. Every other untracked file (one that existed before the loop, or that
the user or another session created during the run) is still backed up and restored, with the same tool-fault note.
A recorded file that a later call deletes leaves the record.

**File**: `claude/.claude/scripts/review/review_loop_coder.py`
**Test**: `tests/scripts/test_review_loop_coder.py` if it exists, else the test file that covers `coder_call` today
(`rg -l coder_call tests/scripts`). Tests: a file the first call creates and the second call deletes stays deleted
with no fault note; a file that existed before the first call and a call deletes is restored with the fault note; a
file that appears between two calls without a coder (written by the test itself between calls) and a call deletes
is restored.

## Phase 2: format_files reads ruff and ruff-format from a pre-commit-only repo

Bug: `repo_configures_ruff` is true only for a ruff.toml, .ruff.toml or a pyproject `[tool.ruff]` table, and
`repo_formats_with_ruff` matches the text `ruff format`. A repo that runs ruff only through
`astral-sh/ruff-pre-commit` (`- id: ruff`, `- id: ruff-format`, no ruff config file) gets no ruff run at all, so the
loop hands back files the pre-commit `ruff-format` hook rewrites. Both real pre-commit configs under `~/dev` have this
shape.

Change: `repo_configures_ruff` is also true when `.pre-commit-config.yaml` names a hook with id `ruff` or
`ruff-format`; `repo_formats_with_ruff` is also true for the hook id `ruff-format`. Read the hook ids through one
function (a line regex on `id:` is enough; the file is YAML but the toolkit has no YAML parser, so match
`^\s*-?\s*id:\s*['"]?(ruff|ruff-format)['"]?\s*$` per line, or the same shape). Copy
`/home/brandon/dev/tldr/.pre-commit-config.yaml` into the test as a fixture.

**File**: `claude/.claude/scripts/lib/format_files.py`
**Test**: `tests/scripts/test_format_files.py` if it exists, else the file that tests `format_files` today
(`rg -l format_files tests/scripts`).

## Phase 3: phase_start moves a stale stop.md aside

Bug: the /code fork writes every stop to `<run folder>/stop.md` with the Write tool. When the file is left over from
an earlier stop and the fork has not read it in this run, Write refuses it, the stop lives only in the reply, and a
later resume reads the old stop.

Change: `phase_start.py` (which the skill runs before every phase's coder, fresh run or resume, after a resume read
the stop) renames an existing `<run folder>/stop.md` to `<run folder>/stop.prev.md` (replacing an older one), so the
next stop is a new file. Name `stop.prev.md` as a constant in `lib/stop_file_names.py`, outside `STOP_FILES` (the
relay relays it only once, as a bounced stop.md not yet relayed). A failed rename prints the error on stderr naming
phase_start and does not stop the script. `review-stop.md` is left alone.

**File**: `claude/.claude/scripts/code/phase_start.py`, `claude/.claude/scripts/lib/stop_file_names.py`
**Test**: `tests/scripts/test_phase_start.py` if it exists, else the file that tests `phase_start` today.

## Plan Deviations

- Rulings by agent-evals-5e, 2026-11-13, on the session-written queue items' done-clauses:
  - Cut "the loop blocks a test removal not on the approved list": no approved-list format exists and the reviewer
    flagged the removal. A new queue item records it: "the loop refuses a test removal that no finding names".
  - "A coder removes its own old copy" and "the loop names leftover run files as one delete list" are replaced by
    Phase 1: a later loop coder may delete the file.
  - Phase 1 covers only files this loop's own coders wrote, recorded per coder call; a file made since the run's start
    by anyone else is still restored (agent-evals-5e overruled the wider "made since run start" rule).
  - "The handback runs pre-commit" is covered by Phase 2.

- Rulings by agent-evals-5e, 2026-11-13: the relay now relays a bounced stop.prev.md once with UNREVIEWED_NOTE (only while the tree is still edited) (plan lines 69-70 and the line-89 ruling amended); and a ruff command with no hook of its kind runs on no files.

- 2026-11-13: Adopt plan change. Ruled by the session, not the user at 2026-11-13 13:03.

  The ruling: AC3's relay stop list means STOP_FILES, which is unchanged; newest_stop also reads stop.prev.md to exit 1 instead of relaying an older stop, and relays a bounced stop.md once from it, with UNREVIEWED_NOTE (only while the tree is still edited). Ruled by the lane session (criteria owner: plan), 2026-11-13.

  The disagreement:
  code_relay.py:53 [plan-drift] — PLAN-IMPACT: AC3 says "`review-stop.md` and the relay's stop list are unchanged", and the plan says stop.prev.md stays outside `STOP_FILES` "(the relay must never relay it)". `STOP_FILES` itself is unchanged, and the relay never relays stop.prev.md. But `newest_stop` now scans `(*STOP_FILES, PREVIOUS_STOP_FILE)`, so the files the relay picks from have changed. Without this, an older review-stop.md would be relayed as new after a /code resume that wrote no stop. The new test `test_a_stop_moved_aside_by_phase_start_is_not_replaced_by_an_older_review_stop` covers that case. Question: does "the relay's stop list" mean only `STOP_FILES`, so this scan is fine under AC3, or does it mean every file the relay looks at? Change if accepted under the second reading: add a line to the plan's `## Plan Deviations` recording who signed off on the relay also reading stop.prev.md, and when. acceptance_criteria: AC3
