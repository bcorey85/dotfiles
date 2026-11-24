---
type: "Change"
change_type: "added"
title: "A lane merge skips the suite rerun when the lane's green run covered the same tree"
description: "Each tests/run.sh run leaves a receipt keyed on the work tree's git tree hash; suite_receipt.py check says skip only when the branch fast-forwards master and its exact tree has a green receipt, so a merge no longer reruns a 5 to 10 minute suite the lane already passed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T13:33:26-06:00"}
seq: 8
kind: "fix"
components: ["script/suite-receipt", "script/run-sh", "script/parallel-tests"]
evidence: ["merge-check-accepts-a-lane-s-green-suite-on-the"]
watches: []
test: "tests/scripts/test_suite_receipt.py::SuiteReceiptTest::test_a_fast_forward_branch_whose_tree_ran_green_skips_the_rerun"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `claude/.claude/scripts/tools/suite_receipt.py`:

- `tree <repo>` hashes the work tree, edits and untracked files that are not ignored included, through a temp index.
- `record` appends `{tree, head, ts, exit, scope, tests, failed}` to `suite-receipts.jsonl` in the common git dir,
  which every worktree shares. It writes nothing when the tree changed during the run.
- `check <repo> <branch> [--base master]` exits 0 (`skip:`) only when the branch fast-forwards the base and the
  latest receipt on `<branch>^{tree}` is green. It exits 1 (`rerun:` with the reason) otherwise: a branch that does
  not fast-forward still gets a trial merge and a suite run.

`tests/run.sh` takes the tree after the lint and records the receipt with the run's overall exit. A failed write
only warns. `tests/parallel_tests.py` writes its counts to `SUITE_SUMMARY_FILE` when that variable is set. The
dotfiles `CLAUDE.md` gets one line that tells the merging session to run `check` before a rerun. That file is the
repo-root one, not a toolkit file under `claude/.claude/`, so no rule-meter run applies.

## Evidence

The 2026-11-22 burn-down reran the suite at about 30 lane merges, 5 to 10 minutes each, and every rerun was green.

## Result

Before the patch the 12 new tests fail: 8 fail and 4 error, because the script and summary file are missing. After
it, all 32 tests in `test_suite_receipt.py`, `test_run_sh.py` and `test_parallel_tests.py` pass, and ruff is clean.

## Watch

None: the skip count lives in the receipts file of this machine's dotfiles checkout, not in a work-log number.

## Back-out

`git revert` the commit. Old receipt files are inert.
