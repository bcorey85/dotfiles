# /code and close-branch batch: fresh agent reports, a cleared hand-off per phase, a close pass that leaves the index alone, no fork commit lines

Fix four queued toolkit defects (`~/agent-evals/queue/code-wait-returns-stale-phase-report.md`,
`stale-handoff-guard-misses-when-the-prior-phase.md`, `close-branch-stages-every-file-with-git-add-a.md`,
`code-fork-report-hands-user-a-commit-command.md`). Each phase starts with a test that fails on the current tree.
Scripts live in `claude/.claude/scripts/` and `claude/.claude/skills/*/scripts/`; tests in `tests/scripts/`, paths
from `tests/scripts/toolkit_paths.py`. Follow `docs/toolkit-script-rules.md` and `claude/.claude/scripts/CLAUDE.md`.

## Scope

- In: `scripts/code/code_wait.py`, `scripts/code/phase_start.py`, `scripts/code/code_review_start.py`,
  `scripts/lib/loop_transcript.py` (a line number for the last text), `scripts/lib/worktree_snapshot.py` (a work-tree
  tree writer), a new `skills/close-branch/scripts/fix_diff.py`, `skills/close-branch/SKILL.md`,
  `skills/code/SKILL.md`, and the tests of each.
- Out: `review/review_asks.py`, `review/phase_asks.py`, `review/review_fix.py` (another lane owns them); the shell
  write gate and `lib/shell_*`; `git_discipline_gate`, `hook_input`, `review_commit_gate`; `settings.json` and every
  CLAUDE.md.

## Phase Status

- [x] Phase 1: `code_wait.py agent` prints only a report no earlier wait printed (risk: medium)
- [x] Phase 2: a phase start moves the last hand-off aside, so a review never starts on an earlier phase's text (risk: medium)
- [x] Phase 3: the close pass records the reviewed tree in a scratch index, never in the user's index (risk: medium)
- [x] Phase 4: the /code stop blocks name the commit step without a command (risk: low)

## Phase 1: `code_wait.py agent` prints only a report no earlier wait printed

Bug: an agent that handed back once and is then resumed with SendMessage still holds its first delivered hand-back in
its transcript, so `agent_finished` is true at once and `wait_agent` prints the old report while the agent works on.
Measured on this machine: the resume reaches the agent's transcript as an `attachment` row of type `queued_command`
(origin kind `coordinator`) 0.1 s to 367 s AFTER the SendMessage call returns, so the transcript alone cannot tell a
resumed agent from a finished one at the first wait.

1. When `wait_agent` prints a report, record which report it printed: the agent id, the transcript line of that report
   (the delivered hand-back's line, or the line of the last text when there is no hand-back) and the time, in one
   small JSON file per agent id under `~/.claude/state/agent-reports/`, keyed only by the agent id and independent of
   cwd (`script_utils.state_file_path` for the name, `write_text_atomically` for the write).
2. An agent counts as finished for a wait only when it is finished and its report line is later than the recorded
   line. With no record, the first finished report prints, as now.
3. `LoopTranscript` gains the transcript line of its last text (`last_text_line`); keep every other field as it is.
4. When the agent is finished but its report is the one already printed and the wait times out, print `STILL_WORKING`
   and, on a second line, that the agent's last report (line N) was printed by an earlier wait at <time>, that this
   wait prints only a newer report, and the transcript path to read when the agent was not resumed.
5. Update the module docstring's `agent` line to say it prints only a report no earlier wait printed.
6. Tests in `tests/scripts/test_code_wait.py`: a fixture transcript with one delivered hand-back: the first wait prints
   it; a second wait on the same transcript does not print it again (WAIT_SECONDS patched short) and prints the
   already-printed line; appending a `queued_command` resume row and a second delivered hand-back makes the next wait
   print the second report. A transcript with no hand-back and a finished meta prints its last text once.

#### Automated Verification

- [ ] Agent wait tests pass - `python3 tests/parallel_tests.py test_code_wait.py`

## Phase 2: a phase start moves the last hand-off aside, so a review never starts on an earlier phase's text

Bug (LED-95, Phase 6): a resumed run started `code_review_start.py` before writing the Phase 6 hand-off block, and
`<run folder>/handoff.txt` still held Phase 5's text. `handoff-phases.json` had no Phase 5 entry, so the digest guard
let the stale text through and recorded it as Phase 6's.

1. `phase_start.py` moves `<run folder>/handoff.txt` to `handoff.prev.txt` (replacing an older one) the same way it
   moves `stop.md` aside, with a reported, non-fatal failure. Name both files once, as constants in `code_wait.py`
   (which both scripts import), and make `code_review_start.py` use that constant.
2. `code_review_start.py`: when the hand-off file is missing, exit non-zero with a message that names the path and says
   to write this phase's hand-off block there with Write, then run the step again. No traceback.
3. Keep the digest guard as it is.
4. Update the `phase_start.py` docstring.
5. Tests: in `tests/scripts/test_phase_start.py`, a run folder holding `handoff.txt` ends with it moved to
   `handoff.prev.txt` and no `handoff.txt`, and an older `handoff.prev.txt` is replaced. In
   `tests/scripts/test_code_review_start.py`, a missing hand-off file exits non-zero with the path in the message and
   no traceback.

#### Automated Verification

- [ ] Phase start and review start tests pass - `python3 tests/parallel_tests.py test_phase_start.py test_code_review_start.py`

## Phase 3: the close pass records the reviewed tree in a scratch index, never in the user's index

Bug: close-branch Step 3 and Step 4 run `git add -A` so the index holds the reviewed tree, then read the fix diff as
`git diff` against the index. That stages every file, so "staged" no longer means "read by the user".

1. `lib/worktree_snapshot.py`: add `work_tree_tree(repo)`: the tree object id of the work tree as it stands, untracked
   files included (gitignored ones left out), built with `git add -A` and `git write-tree` in a scratch index seeded
   from a copy of the real index (`GIT_INDEX_FILE`), in a temporary folder removed afterwards. The real index is never
   written. Raise a named error naming the git call when one fails.
2. New `claude/.claude/skills/close-branch/scripts/fix_diff.py`, run from the repo root:
   - `mark`: writes the current `work_tree_tree` id to `<git dir>/close-branch/reviewed-tree` (atomic write) and
     prints it.
   - `show`: reads that id (no file → exit 2 naming `fix_diff.py mark`), takes the current `work_tree_tree`, and prints
     one JSON object: `reviewed_tree`, `fixed_tree`, `diff_command` (`git diff <reviewed> <fixed>`), and `files` (the
     paths that command lists, from `git diff --name-only`).
3. `skills/close-branch/SKILL.md`: Step 3 and Step 4's fail route run `python3 ~/.claude/skills/close-branch/scripts/fix_diff.py mark`
   in place of `git add -A`, and say the index stays as the user left it. Step 4 defines the fix diff as the
   `diff_command` that `fix_diff.py show` prints, and the gate prompt names that command and its `files` in place of
   "`git diff` (working tree against the index) and these new files". The description and steps agree. Write no
   rationale into the skill.
4. Tests: new `tests/scripts/test_fix_diff.py` (script path in `toolkit_paths.py`): in a scratch repo with one staged
   file and one unstaged edit, `mark`, then edit a tracked file and add a new file, then `show`: `files` lists exactly
   the edited and the new file, and `git diff --cached --name-only` is the same before and after both calls; `show`
   before `mark` exits 2. In `tests/scripts/test_worktree_snapshot.py`: `work_tree_tree` leaves the real index file's
   bytes unchanged and puts an untracked file in the tree.

#### Automated Verification

- [ ] Fix-diff and snapshot tests pass - `python3 tests/parallel_tests.py test_fix_diff.py test_worktree_snapshot.py`

## Phase 4: the /code stop blocks name the commit step without a command

Bug: blocks B and C in `skills/code/SKILL.md` print `! git commit -m "<subject>"`. The fork writes it and the main
session relays the stop word for word, so a subagent hands the user a command.

1. `skills/code/SKILL.md`: the sentence after the phase-boundary list, block B's Next step 2 and block C's Next line
   name the commit subject (the phase's `Commit` line, else `<ticket id>: Phase <N>: <phase title>`) as `Commit
   subject: <subject>` and write no `!` line and no `git commit` command. Nothing else in the file changes.
2. New test `tests/scripts/test_code_skill_text.py`: no line of `skills/code/SKILL.md` or `agents/code-fork.md`
   holds a `! git` command or a `git commit` command.

#### Automated Verification

- [x] Skill text test passes - `python3 tests/parallel_tests.py test_code_skill_text.py`

#### Manual Verification

- [ ] Human-only: a fixture run of a /code fork ends its report with no `!` git line (rule-meter run or the user's call).

## Plan Deviations

Phase 2 ruling (session, 2026-11-17): a resume that re-enters step 3 runs phase_start.py, which moves the phase's hand-off to handoff.prev.txt; the skill's Resume line names handoff.prev.txt. AC3 still met.
Phase 1 record location: keyed by agent id outside the repo, ruled by the lane session (fix/code-wait-handoff-and-close-branch), 2026-11-18.
Phase 3 ruling (session, 2026-11-18, owner plan; no criterion's meaning changed): work_tree_tree stays in lib/worktree_snapshot.py as the plan names it, since it returns a git tree object id, not the sha256 tree_fingerprint; the scripts/CLAUDE.md "Tree identity" owner line is out of scope for this branch and needs a later one-line extension.
