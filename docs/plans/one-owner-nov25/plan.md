# One owner: the pre-commit drift baseline, and prune's keep verdict for lane close

Two queue items where two places keep their own copy of one decision, or one check judges a commit by state it did
not add. Each phase starts with a test that fails on the current tree. Tests live in `tests/scripts/`.

Queue items: `pre-commit-drift-check-refuses-every-toolkit` (Phase 1),
`herdr-lane-resume-close-keeps-its-own-copy-of-the` (Phases 2 and 3).

## Scope

- In: `.githooks/pre-commit`, `scripts/.local/bin/herdr-worktree-prune`, new Python modules under
  `scripts/.local/lib/` split out of prune, `scripts/.local/bin/herdr-lane-resume`, and their tests
  (`tests/scripts/test_pre_commit_hook.py`, `tests/scripts/test_herdr_worktree_prune.py`,
  `tests/scripts/test_herdr_lane_resume.py`). `CLAUDE.md` is not edited.
- Out: `claude/.claude/scripts/review/review_loop_*`, `review_fix*`, `gates/`, `skills/`, `lane_status`, and
  `~/agent-evals/bin/toolkit_drift.py` (its output format stays as it is).

## Phase Status

- [x] Phase 1: the pre-commit drift check refuses only drift the commit adds (risk: low)
- [ ] Phase 2: split herdr-worktree-prune by concern so it has room for a verb (risk: medium)
- [ ] Phase 3: lane close reads prune's keep verdict for the tree (risk: medium)

## Phase 1: the pre-commit drift check refuses only drift the commit adds

Bug: `.githooks/pre-commit` runs `toolkit_drift.py` on the staged `claude/.claude/*.md` tree and exits 1 on any
problem. Drift already present at HEAD (an agent-evals-side change, such as one extra name in `toolkit_skills.txt`)
then refuses every toolkit prose commit, even one that does not touch the stale entry.

1. When the staged run exits non-zero, run the same check on HEAD's `claude/.claude/*.md` tree, exported the same way
   (a temporary index read from HEAD, then the same `ls-files | checkout-index` pipeline). Both exports go through one
   shell function.
2. The commit is refused only when the staged run prints a problem line (stderr) that the HEAD run does not print.
   The refusal prints only the added lines. A staged run whose drift is all already at HEAD passes, with one note on
   stderr that names the count of drift lines already at HEAD.
3. Fail closed: with no HEAD commit, or when the HEAD run exits 0 while the staged run fails, every staged problem
   counts as added. A staged-run output line that does not start with `toolkit_drift: ` counts as added (a crash is
   never passed as old drift).

4. Tests in the pre-commit test file, with a drift stub that prints one problem line per CLAUDE.md line starting
   `stale`: drift at HEAD plus a commit that adds none passes; a commit that adds a drift line is refused and names
   only the added line; a commit that shrinks drift passes. The first and third fail on the current hook.

#### Automated Verification

- [ ] **Hook tests**: the pre-commit tests pass - `python3 tests/parallel_tests.py test_pre_commit_hook.py`

## Phase 2: split herdr-worktree-prune by concern so it has room for a verb

`herdr-worktree-prune` is 991 lines; the toolkit size rule forbids adding a verb that takes a script past 1000 lines
without a split first. No behavior change in this phase.

1. Move the git runner and worktree-list base (`Result`, `run`, `git`, `real`, `inside`, `show`, `PruneError`,
   `Worktree`, `parse_worktrees` and its helpers, `list_worktrees`, `Repo`, `Tally`, `HEADS_PREFIX`) into
   `scripts/.local/lib/worktree_git.py`.
2. Move branch deletion and branch mode (`BranchDeletion` through `prune_branches`) into
   `scripts/.local/lib/worktree_branches.py`, importing the base.
3. Prune finds `scripts/.local/lib` from `pathlib.Path(__file__).resolve()` (a stow symlink resolves to the repo) and
   imports the moved names, so the names the tests read on the loaded prune module stay reachable there. The keep
   rules (`check_*`, `CHECKS`, `evaluate`) stay in prune.
4. Lint (`bash tests/lint.sh`) covers the two new `.py` files.

#### Automated Verification

- [ ] **Prune tests**: pass unchanged - `python3 tests/parallel_tests.py test_herdr_worktree_prune.py`
- [ ] **Lane-resume tests**: pass unchanged - `python3 tests/parallel_tests.py test_herdr_lane_resume.py`
- [ ] **Agent-run**: prune is under 800 lines by wc -l

## Phase 3: lane close reads prune's keep verdict for the tree

Bug: `herdr-lane-resume`'s entry-less close keeps its own copy of part of prune's keep rules (`branch_is_merged` and a
`git status --porcelain` dirty check) and the copies differ (close ignores stashes, submodules, nested repos, locks).

1. `herdr-worktree-prune --check <path>`: judge the one linked worktree at `<path>` with prune's own `evaluate`, over
   the checks of the tree's own state: every check in `CHECKS` except the occupancy checks (current worktree, open
   lane, process, herdr), which a close clears itself by closing the workspace. It runs the same start-up (fetch of
   origin/<default>) and reads only the worktree list and stashes. It prints one JSON object on stdout:
   `{"path", "branch", "verdict": "remove"|"keep", "code", "reason"}` (`code` and `reason` null on `remove`) and exits
   0. A path that is not a worktree entry of the repo, and any `PruneError`, exits 1 with the message on stderr.
   The docstring documents the verb.
2. `herdr-lane-resume` entry-less close: after the working-agent check and before any workspace closes, run
   `herdr-worktree-prune --check <wt>` from the main checkout. A `keep` verdict refuses, changing nothing, with prune's
   reason in the message; a failed check refuses the same way. Delete `branch_is_merged` and the dirty check. Update
   the header comment's refusal list.
3. The lane-resume test stub for prune hands `--check` to the real prune script (path from an environment variable
   that defaults to the tree the tests sit in) and records no event for it; the other calls stay stubbed.

4. Prune tests: the check verb on merged clean, merged dirty, unmerged and squash-merged trees gives remove, keep
   (uncommitted changes), keep (not merged), keep (not merged); each verdict and reason equals the list-mode line for
   the same tree when no workspace, agent or process is on it; a herdr workspace on a merged clean tree still gives
   remove; a path that is not a worktree exits 1.
5. Lane-resume tests: the same four states through the close verb: only merged clean closes and prunes; the others
   refuse before any close with prune's reason. A stash on a merged clean branch now refuses the close (fails before
   the change). Existing refusal tests read prune's messages.

#### Automated Verification

- [ ] **Prune tests**: the check verb tests pass - `python3 tests/parallel_tests.py test_herdr_worktree_prune.py`
- [ ] **Lane-resume tests**: the close tests pass - `python3 tests/parallel_tests.py test_herdr_lane_resume.py`

## Branch end

- `bash tests/run.sh` under the memory cap passes; `bash tests/lint.sh` on the changed `.py` files passes.
- One change file per behavior change (Phase 1, Phase 3).
