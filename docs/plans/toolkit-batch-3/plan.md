# Toolkit batch 3: safer pulls, per-phase handoffs, moved fix lines, the removal stop route, Step 1 review rows

Fix five queued toolkit defects. Each phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

## Scope

- In: `tools/pull_keep_index.py`, `code/code_review_start.py`, `lib/change_removal.py`, `review/review_loop_plan.py`,
  `review/review_loop_script.py` (the removal call only), `code/code_wait.py`, `review/verify-log`, their tests, and
  one change note per fix in `docs/changes/notes/`.
- Out: prompt files under `claude/.claude/agents/` and `claude/.claude/skills/` (a prompt rule needs rule-meter runs).
  Dropped in triage: the review-commit-gate item (the gate was right: the fork applied asks with no re-review) and the
  ask-ruling `--by user` item (only a prompt rule fixes it). The verify-prep plan folder item was already fixed on
  master.

## Phase Status

- [x] Phase 1: pull_keep_index merges the remote when a rebase replay re-conflicts (risk: medium)
- [x] Phase 2: code_review_start stops on a handoff an earlier phase read (risk: low)
- [x] Phase 3: the removed-change guard counts moved and edited lines as kept (risk: medium)
- [x] Phase 4: code_wait prints the next step for a fix-removed-change stop (risk: low)
- [x] Phase 5: verify-log logs Step 1 review rows when only a commit review covers the tree (risk: low)

## Phase 1: pull_keep_index merges the remote when a rebase replay re-conflicts

Bug: on a branch that merged master with resolved conflicts, the pull's rebase replays those merges and stops on the
same conflicts. When `git merge-tree --write-tree` says a merge of FETCH_HEAD into the branch tip is clean, abort the
rebase and merge instead; otherwise keep the old stop.

**File**: `claude/.claude/scripts/tools/pull_keep_index.py`
**Test**: `tests/scripts/test_pull_keep_index.py`

## Phase 2: code_review_start stops on a handoff an earlier phase read

Bug: the fork wrote Phase 4's handoff to another path, and the review read Phase 3's handoff. Record
`{sha256 of handoff text: "<plan>#<phase>"}` in `<run folder>/handoff-phases.json`; a live start whose text an earlier
phase of the same plan read exits 1 and names `<run folder>/handoff.txt`. A rerun of one phase passes, the same text
under another plan passes, and a dry run records nothing.

**File**: `claude/.claude/scripts/code/code_review_start.py`
**Test**: `tests/scripts/test_code_review_start.py`

## Phase 3: the removed-change guard counts moved and edited lines as kept

Bug: a fix pass that moved a block and edited it on the way tripped `fix-removed-change`. The guard fires on removed
lines less the removed lines the fix passes wrote again as near copies (difflib ratio ≥ 0.8); a line moved unchanged
(a rename) is not new.

**File**: `claude/.claude/scripts/lib/change_removal.py`, `claude/.claude/scripts/review/review_loop_plan.py`,
`claude/.claude/scripts/review/review_loop_script.py`
**Test**: `tests/scripts/test_change_removal.py`

## Phase 4: code_wait prints the next step for a fix-removed-change stop

Bug: /code had no route for the stop. `code_wait.py review` reads the packet and, on `fix-removed-change`, prints a
STOP line (write the blockers to `<run folder>/stop.md`; `/code resume <plan path>` re-runs the review) and exits 1.

**File**: `claude/.claude/scripts/code/code_wait.py`
**Test**: `tests/scripts/test_code_wait.py`

## Phase 5: verify-log logs Step 1 review rows when only a commit review covers the tree

Bug: verify-log refused Step 1's rows with "already counts" when only a converged commit review covered the tree. The
refusal fires only when a branch review covers it.

**File**: `claude/.claude/scripts/review/verify-log`
**Test**: `tests/scripts/test_verify_branch_script.py`

## Plan Deviations

- Phase 3 rule: the guard subtracts only the removed lines the fix passes wrote again as near copies, not every new
  line. Ruled by agent-evals-5e, 2026-11-12 (review ask 1, accepted).
- Phase 3 threshold: `REWRITE_SIMILARITY` rises from 0.6 to 0.8, with a test where same-style unrelated code replacing
  a deleted block still trips `is_gutted`. Ruled by agent-evals-5e, 2026-11-12 (review ask 2, accepted).
