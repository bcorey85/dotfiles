# Review launch: a merge-free review base

`review/review_launch.py` resolves `--base` with `resolved_base` alone, so a /review on a branch that merged master
after its base, given that older base, reviews master's merged-in lines as the branch's own. `code/code_review_start.py`
already folds merged-in commits out through `lib/merge_free_base.py` `merge_free_base`. Route review_launch's base
through the same owner. Queue item: `~/agent-evals/queue/review-launch-diffs-merged-in-master-changes-when.md`.

## Scope

- In: `review/review_launch.py` (`resolved_base`, plus the edits below), `tests/scripts/test_review_launch.py`, a change
  file under `docs/changes`.
  Also in, as three small edits beyond `resolved_base`: the `--base` help text in `launch_parser` (it must say merged-in
  changes are left out); an empty-scope stop in `command_launch` when `--base` was given (the merge-free base can empty
  the scope with no work-tree change); and the conflict message in `code/code_review_start.py` `diff_base` (its trailing
  period is no longer doubled). The open lanes feature/hunk-phase-notes and feature/review-fix-fork edit
  `command_launch`, so their owners need to know it changed.
- Out: every other part of review_launch.py; `lib/merge_free_base.py` (no change needed); the review loop.

## Phase Status

- [x] Phase 1: review_launch reads the base through merge_free_base (risk: low)

## Phase 1: review_launch reads the base through merge_free_base

1. `resolved_base(repo, base)`: after `rev-parse` finds the commit, return `merge_free_base.merge_free_base(repo,
   commit)`. Import `merge_free_base` (lib is already on sys.path). Never copy its logic.
2. `merge_free_base.MergeConflictError` raises `LaunchError` naming the merge and the recovery (resolve or revert the
   merge, or pass a `--base` after it); `MergeBaseGitError` raises `LaunchError` with the git error. Nothing is
   launched in either case.
3. The prompt header's `base:` then names the merge-free commit, so `check_files_exist`, `review_files` and the loop
   all diff against it.
4. `launch_parser`: the `--base` help text says merged-in changes are left out.
5. `command_launch`: when `--base` was given and the scope is empty, stop with an empty-scope error (the merge-free
   base can empty the scope with no work-tree change).
6. `code/code_review_start.py` `diff_base`: drop the doubled trailing period in the conflict message.

#### Automated Verification

- New test in `tests/scripts/test_review_launch.py`: a repo whose branch commits its own file, then merges a side
  branch (standing in for master) that adds another file; `launch --base <older base>` writes a prompt whose `base:`
  diff against the work tree lists only the branch's own files, not the merged-in file. The test fails on the current
  tree.
- A test that a merged-in parent which conflicts with the base stops the launch with exit non-zero and names the merge.
- A test that a launch base whose only later change is a merge stops with an empty-scope error
  (`test_a_launch_base_whose_only_later_change_is_a_merge_stops_with_an_empty_scope`).
- A test that a failing git call stops the launch with git's error (`ResolvedBaseGitErrorTest`).
- `python3 tests/parallel_tests.py test_review_launch.py` passes; `bash tests/lint.sh` on the changed .py passes.

## Plan Deviations

- 2026-11-26: Adopt plan change. Ruled by the session, not the user at 2026-11-26 05:45.

  The ruling: Session adopts the plan scope widening: help text, empty-scope stop in command_launch and diff_base period fix are in scope; no acceptance criterion changes.

  The disagreement:
  PLAN-IMPACT: docs/plans/review-launch-merge-free-base/plan.md:10-12 [plan-drift] — Scope says In is "`review/review_launch.py` (`resolved_base` only)" and Out is "every other part of review_launch.py (open lanes feature/hunk-phase-notes and feature/review-fix-fork edit it)". The diff still edits `command_launch` (review_launch.py:619-621) and the `--base` help in `launch_parser` (review_launch.py:108-109). It also edits `code/code_review_start.py:409-410`, which the plan does not list at all. The `command_launch` edit sits in the empty-scope block, where the open lanes may conflict. Either widen the plan's In list (and its Phase 1 steps) to cover these three edits, or move them out of this change.
