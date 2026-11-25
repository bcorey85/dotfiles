# code-step-scripts-nov25: resume base after a ticked phase, plan-folder rulings, phase-end change-file check, denied coder git writes

Fix four /code-step defects. Each script phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`. Follow
`docs/toolkit-script-rules.md`.

## Scope

- In: `code/phase_start.py`, `lib/plan_format.py` (`append_deviation` only), `.githooks/pre-commit` (its change-file
  block only, lines 9-23), a new `.githooks/change-file-check`, a new `code/phase_change_file.py`,
  `skills/code/SKILL.md`, `skills/code/phase-end-block.md` if a block changes, and the tests of each.
- Out: `review/review_loop_*`, `review/review_fix_plan_impacts.py` (another lane edits it), `gates/`, the `stage`
  skill, and the drift-check block of `.githooks/pre-commit` (lines 25-41; another lane edits it).

## Phase Status

- [ ] Phase 1: a resume after a ticked phase starts a new record at HEAD (risk: medium)
- [ ] Phase 2: review_fix decide accepts a plan folder (risk: low)
- [ ] Phase 3: the phase end runs the change-file check (risk: medium)
- [ ] Phase 4: a coder's denied git write does not stop the run (risk: low)

## Phase 1: a resume after a ticked phase starts a new record at HEAD

Bug: after Phase N was committed, `/code resume` for Phase N+1 ran `phase_start.py --resume`, which kept the start
record (its head an ancestor of HEAD) and printed Phase N's start head as the base. The resume of the same phase is
right to keep it; a resume after the phase was ticked is not.

1. `resume_base(repo, kept)`: when the kept head is an ancestor of HEAD and differs from it, find each `.md` file that
   changed between the kept head and HEAD (`git diff --name-only <kept> HEAD -- '*.md'`, through
   `script_utils.git_output`). For each, read its text at both commits (`git show <commit>:<path>`; missing at the old
   commit counts as no phases) and parse the `## Phase Status` entries with `plan_format.phase_status_entries`. A
   phase number that is done at HEAD and not done at the kept head is a tick.
2. On a tick, print one stderr line naming the plan path and the phase number ("phase N of <path> was ticked since the
   start record; starting a new record at HEAD") and return None, so `main` takes the existing path that writes a new
   record at HEAD and prints HEAD.
3. A file whose phase status does not parse raises nothing new: read it the way the existing callers of
   `phase_status_entries` do. Update the module docstring's `--resume` paragraph.

#### Automated Verification

- [ ] **Agent-run**: new tests in test_phase_start.py: a start record at commit H0, then a commit that ticks Phase 1
  in `docs/plans/x/plan.md`; `--resume` prints the new HEAD and the record's head is HEAD (fails before the change). A
  commit that ticks no phase keeps H0 as the printed base.
- [ ] **Tests**: `python3 tests/parallel_tests.py test_phase_start.py`

## Phase 2: review_fix decide accepts a plan folder

Bug: `review_fix.py decide --plan <plan dir>` crashes with IsADirectoryError in `plan_format.append_deviation`, which
calls `read_text()` on the folder.

1. `plan_format.append_deviation(plan_path, entry)`: resolve the path through `plan_file_of(plan_path)` first, so a
   folder writes to the plan file inside it. A folder with no plan file raises the `PlanFormatError` that
   `plan_file_of` raises; check that `review_fix.py`'s caller reports it as it reports other plan errors.
2. Do not edit `review/review_fix_plan_impacts.py`.

#### Automated Verification

- [ ] **Agent-run**: a new test in test_plan_format.py beside the append_deviation tests: a folder holding plan.md
  gets the Plan Deviations entry in plan.md (fails before the change).
- [ ] **Tests**: `python3 tests/parallel_tests.py test_plan_format.py test_plan_check.py`

## Phase 3: the phase end runs the change-file check

Bug: a /code phase changed toolkit files and printed a commit subject with no change file; the pre-commit hook then
refused the commit.

1. New executable `.githooks/change-file-check` (bash, `set -euo pipefail`): reads `git diff --name-status`-style
   lines (`<status letter>\t<path>`) on stdin and owns `toolkit_pattern` and `change_file_pattern` (moved from
   `pre-commit`). A toolkit path with no added or modified change-note path prints the same refusal text the hook
   prints today and exits 1; else exits 0.
2. `.githooks/pre-commit`: its change-file block becomes one call:
   `git diff --cached --name-status --no-renames | "$hooks_dir/change-file-check"`, with the hooks folder found from
   the hook's own path. Leave the drift block untouched.
3. New `claude/.claude/scripts/code/phase_change_file.py`, run from the repo root: when `<repo top>/.githooks/
   change-file-check` is absent, print `no change-file check in this repo` and exit 0. Else feed it the work tree's
   changes against HEAD (`git diff --name-status --no-renames HEAD`, plus each untracked file from
   `git ls-files --others --exclude-standard` as `A\t<path>`) and pass its output through. On exit 1, add a last line:
   `Dispatch a coder to file the change file with that command, then run phase_change_file.py again.` and exit 1.
4. `skills/code/SKILL.md`, step 2's Phase Status tick bullet: before the tick coder, run
   `python3 ~/.claude/scripts/code/phase_change_file.py` from the repo root; on exit 1, do the step its last line names.
   Rules on wording: no rationale, one line.

#### Automated Verification

- [ ] **Agent-run**: new test_phase_change_file.py: a fixture repo with the check installed and an untracked toolkit
  file exits 1 naming the path; an added untracked change note under docs/changes/notes exits 0; a repo without the
  check exits 0 (fails before the change: the script does not exist). test_pre_commit_hook.py passes unchanged.
- [ ] **Tests**: `python3 tests/parallel_tests.py test_phase_change_file.py test_pre_commit_hook.py`

## Phase 4: a coder's denied git write does not stop the run

Bug: a fork copied the task's "commit with a pathspec" into its coder's prompt; the git gate denied the coder's
`git add`, and the fork stopped before review with nothing committed.

1. `skills/code/SKILL.md` step 3: add that the coder's prompt holds no stage or commit step; a commit the task asks for
   becomes the phase-end commit subject. Add that a coder's report of a denied git write is no STOP: go on to step 4
   with the changes uncommitted.
2. Keep each new rule to one sentence, with no rationale. Run `rule-anchors.sh list` and `check` on the skill file if it
   is anchored.
3. `tests/scripts/test_code_skill_text.py`: a test that the skill holds both sentences.

#### Automated Verification

- [ ] **Agent-run**: the new skill-text test fails before the change.
- [ ] **Tests**: `python3 tests/parallel_tests.py test_code_skill_text.py`
