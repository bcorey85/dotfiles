# One owner: the pre-commit drift baseline, and prune's keep verdict for lane close

Two queue items where two places keep their own copy of one decision, or one check judges a commit by state it did
not add. Each phase starts with a test that fails on the current tree. Tests live in `tests/scripts/`.

Queue items: `pre-commit-drift-check-refuses-every-toolkit` (Phase 1),
`herdr-lane-resume-close-keeps-its-own-copy-of-the` (Phases 2 and 3),
`move-review-launch-wait-for-exit-onto-process` (Phase 4), and the memory_cap_scope half of
`quality-check-cap-keeps-its-own-copy-of-the-shell` (Phase 5; the split is in `03-decisions.md`).

## Scope

- In: `.githooks/pre-commit`, `scripts/.local/bin/herdr-worktree-prune`, new Python modules under
  `scripts/.local/lib/` split out of prune, `scripts/.local/bin/herdr-lane-resume`, and their tests
  (`tests/scripts/test_pre_commit_hook.py`, `tests/scripts/test_herdr_worktree_prune.py`,
  `tests/scripts/test_herdr_lane_resume.py`); `claude/.claude/scripts/review/review_launch.py`,
  `claude/.claude/scripts/lib/process_group.py`, `claude/.claude/scripts/code/fork_children.py`,
  `claude/.claude/scripts/lib/shell_command.py`, `claude/.claude/scripts/lib/memory_cap_scope.py` and their tests.
  `CLAUDE.md` is not edited.
- Out: `claude/.claude/scripts/review/review_loop_*`, `review_fix*`, `gates/`, `skills/`, `lane_status`, and
  `~/agent-evals/bin/toolkit_drift.py` (its output format stays as it is).

## Phase Status

- [x] Phase 1: the pre-commit drift check refuses only drift the commit adds (risk: low)
- [x] Phase 2: split herdr-worktree-prune by concern so it has room for a verb (risk: medium)
- [x] Phase 3: lane close reads prune's keep verdict for the tree (risk: medium)
- [ ] Phase 4: review_launch waits on the stopped loop's whole group through process_group (risk: low)
- [ ] Phase 5: memory_cap_scope reads systemd-run options through shell_command's option walk (risk: low)

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

## Phase 4: review_launch waits on the stopped loop's whole group through process_group

Bug: `review/review_launch.py` `wait_for_exit` keeps its own poll loop and polls only the leader pid after
`terminate_group`, so a child that outlives the leader is not waited on. `process_group.wait_until_group_gone` already
polls the whole group. The stop wait is 5 s there and 2 s in `code/fork_children.py`.

1. `lib/process_group.py` owns one `STOP_WAIT_SECONDS = 5`: the wait for a stopped group to exit, long enough for a
   review loop to remove its worktrees. `review_launch.py` and `code/fork_children.py` drop their own constants and
   read it.
2. `stop_loop` reads `process_group.group_id(pid)` before `terminate_group`, then calls
   `process_group.wait_until_group_gone(group, process_group.STOP_WAIT_SECONDS)`; on False it prints the same
   still-running line on stderr and the launch goes on. Delete `wait_for_exit` and `STOP_POLL_SECONDS`.
3. Test in the review_launch tests: a real process group whose leader exits on SIGTERM while a child ignores it for a
   moment; `stop_loop` returns only after the child is gone (fails before the change). Update the existing stop tests
   that patch `STOP_WAIT_SECONDS`/`STOP_POLL_SECONDS` to patch the owner.

#### Automated Verification

- [ ] **Launch tests**: pass - `python3 tests/parallel_tests.py test_review_launch.py`
- [ ] **Fork children tests**: pass - `python3 tests/parallel_tests.py test_fork_children.py`
- [ ] **Process group tests**: pass - `python3 tests/parallel_tests.py test_process_group.py`

## Phase 5: memory_cap_scope reads systemd-run options through shell_command's option walk

Bug: `lib/memory_cap_scope.py` `systemd_run_slice` walks the systemd-run options with its own loop, repeating
`shell_command.git_options` and `git_option_values`.

1. In `lib/shell_command.py`, generalize the walk: `command_options(words, value_options, start=1)` returns the
   (option, value) pairs and the index after them; `git_options(words)` becomes `command_options(words,
   GIT_VALUE_OPTIONS)`. Rename nothing else; `git_option_values` reads any such pair list (docstring says so).
2. `memory_cap_scope.systemd_run_slice` returns the last value of
   `git_option_values(command_options(words, SYSTEMD_RUN_VALUE_OPTIONS)[0], "--slice")`, or None;
   `systemd_run_options_end` returns `command_options(...)[1]`. Its own loop is deleted.
3. Tests: `command_options` on a systemd-run word list with `--slice x`, `--slice=y`, `-p "X=$(cmd)"` and the program
   after; memory_cap_scope tests pass unchanged.

#### Automated Verification

- [ ] **Shell command tests**: pass - `python3 tests/parallel_tests.py test_shell_command.py`
- [ ] **Memory cap tests**: pass - `python3 tests/parallel_tests.py test_memory_cap_scope.py`

## Branch end

- `bash tests/run.sh` under the memory cap passes; `bash tests/lint.sh` on the changed `.py` files passes.
- One change file per behavior change (Phase 1, Phase 3, Phase 4 with the stop-wait pick and its reason, Phase 5).
