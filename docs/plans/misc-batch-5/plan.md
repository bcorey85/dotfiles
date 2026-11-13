# Misc batch 5: outward closing questions, module-sized simplify slices, one missing-helpers error

Fix three queued toolkit defects. Each phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/` and `claude/.claude/skills/refactor/scripts/`; tests in `tests/scripts/`, paths from
`tests/scripts/toolkit_paths.py`.

## Scope

- In: `scripts/gates/permission_question.py`, `skills/refactor/scripts/refactor_flow.py` (simplify-prep only) and one
  new module beside it, `scripts/.local/bin/herdr-worktree`, their tests.
- Out: prompt files under `claude/.claude/agents/` and `claude/.claude/skills/` (a prompt rule needs rule-meter
  runs); `skills/code`, `agents/coder.md` (another lane). Dropped in triage: the profiling compose collision (one
  work-machine sighting with no command shape to guard, and its done-clause asks a brief rule in skills/code), the
  worktree-on-a-ticket-ask item (a prompt rule, already applied live; its check is a rule-meter eval). Refactor
  branch-prep already reads staged, unstaged and untracked files on master (9475032b); only the simplify slicing is
  still broken.

## Phase Status

- [x] Phase 1: a closing question that names an outside destination passes the permission gate (risk: low)
- [x] Phase 2: simplify-prep counts source files only and slices along module folders (risk: medium)
- [x] Phase 3: herdr-worktree names every missing helper in one error with the stow command (risk: low)

## Phase 1: a closing question that names an outside destination passes the permission gate

Bug: the Stop gate blocked a closing question that asked whether to post to a public PR, and on this machine it blocks
"Want me to add your data to vkd3d-proton #3304?" and "do you want that name off GitHub?". These ask before a step that
leaves the machine. `OUTWARD_STEP` gains one alternative: a question that names an outside destination after `to`,
`on`, `in` or `off`, with at most two words between (`the`, `this`, `that`, `your` and any name), where the destination
is `PR`, `MR`, `pull request`, `merge request`, `issue`, `ticket`, `thread`, `GitHub`, `GitLab`, `Jira`, `Linear`,
`upstream` or `#<number>`. It also gains `public`/`publicly`. Update the module docstring to say so.

Still blocked: "Shall I start #914?" (no preposition), "Want me to fix them now on a new branch?", "Want me to add a
comment to the function?", "Want me to look into the issue?" (`into` is not in the list).

Tests in `tests/scripts/test_staged_claim_gate.py` beside `test_a_question_about_an_outward_or_lasting_step_passes`:
the passing questions above plus "Want me to leave that as a comment on PR #412?" and "Want me to leave a public
comment?", and the still-blocked ones.

**File**: `claude/.claude/scripts/gates/permission_question.py`
**Test**: `tests/scripts/test_staged_claim_gate.py`

## Phase 2: simplify-prep counts source files only and slices along module folders

Bug: simplify-prep split a feature folder into 25-file alphabetical slices (17 slices, tests and index files
included), which cut modules apart. Put the slicing in a new module `skills/refactor/scripts/simplify_slices.py` (the
flow script is over 1000 lines) and call it from `simplify_prep`:

- Drop from the file list: test files (`source_paths.is_test_path`), index files (`index.<js|jsx|ts|tsx|mjs|cjs>`,
  `__init__.py`) and style files (`.css`, `.scss`, `.sass`, `.less`, `.styl`, `.pcss`). Print how many of each kind
  were dropped. When nothing is left, print the existing `STOP:` form naming the target and saying only test, index
  or style files remain.
- Group the rest by module folder: the first path part below the target folder (a file right in the target folder is
  its own group; a target that is a file is its own group). Pack whole groups, in sorted order, into slices of at most
  `MAX_SIMPLIFY_FILES`; a group never splits across slices while it fits in one. A group over the limit splits by its
  own next-level folders the same way; a folder over the limit with no subfolders splits into sorted chunks.
- Each slice's printed line names the module folders it holds. `--slice N` and the range error keep their form.

Tests: a target with 30 source files in three module folders plus tests, index and style files gives slices that
never cut a module folder and never list a test, index or style file; a 30-file folder with no subfolders still
chunks; a target with only test files stops.

**File**: `claude/.claude/skills/refactor/scripts/refactor_flow.py`, `claude/.claude/skills/refactor/scripts/simplify_slices.py`
**Test**: `tests/scripts/test_refactor_flow.py`

## Phase 3: herdr-worktree names every missing helper in one error with the stow command

Bug: the `--fork` helper check exits at the first helper missing from the bin folder, so a session reran it once per
helper. Collect every missing helper (`detach`, `herdr-worktree-watch`), then print one error that names each and the
exact command that links them: `stow -d <dotfiles> -t "$HOME" -R scripts`, where `<dotfiles>` is the checkout that
holds the script's real file (three folders above `scripts/.local/bin/herdr-worktree` after resolving links). Still
exits 1 before anything is created.

Tests: update `test_a_fork_with_a_helper_not_yet_stowed_fails_naming_it_and_prints_no_watch_line` to the new message;
add a test where both helpers are missing and one run names both and the stow command.

**File**: `scripts/.local/bin/herdr-worktree`
**Test**: `tests/scripts/test_herdr_worktree.py`

## Plan Deviations

- Phase 1 ruling (AC1, owner plan, session, 2026-11-13): GitHub, GitLab and case-sensitive Linear count as destinations only after `to`, `in` or `off` (not `on`), and not before GitHub Actions, workflows, CLI, Pages, docs, API, Copilot, Desktop, Codespaces, packages, gist or interpolation, so existing sent-back cases (`look it up on GitHub`, `check the GitHub Actions log`, `switch ... to linear`) stay blocked; AC1's named pass cases still pass.
- Phase 1 ruling (AC1, owner plan, session, 2026-11-13): the opening phrase (`want me to`, `ready to`, `do you want it to`) is excluded from the outward-step search, `to` after try/start/begin/need/have/going is an infinitive, and a destination may not be followed by a word character, `-`, `.` or `/` word (file names like `issues.py` stay local).
- Phase 1 ruling (AC1, owner plan, session, 2026-11-13): bare `public`/`publicly` stays as the plan states; known residual: `make the helper public?` passes. Mid-question infinitive `to` ("go back to review the PR") stays as the plan's "any name" grammar. Rejected both narrowings as against the plan's wording; revisit only if a session hits them.
- Phase 2 ruling: simplify-prep also drops the files `source_paths.is_uncounted_path` rejects (generated, lockfiles), so its count matches the owner's definition of source. Ruled by dotfiles-misc-batch-5 (session), 2026-11-13 (branch review ask; AC2 holds either way).
