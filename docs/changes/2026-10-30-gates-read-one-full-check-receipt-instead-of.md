---
type: "Change"
change_type: "fixed"
title: "Gates read one full-check receipt instead of matching command text"
description: "full_check.py runs only the repo's declared check and writes a receipt per work tree; the review-loop backstop, handback's deny, the phase-end whole-suite skip and verify-prep read that receipt for the tree as it stands, so a scoped, killed or stale run no longer passes as a full check."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T00:05:17-05:00"}
seq: 333
kind: "fix"
components: ["script/full-check", "script/review-loop-gate", "script/handback", "script/code-step", "script/verify-branch", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check_receipt.py::FullCheckRunRowsTest::test_a_scoped_run_that_exits_zero_never_gets_full_suite_credit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `full_check.py` runs only the repo's declared `Quality check:` command, with expected-red steps left out. A command
  handed to it is ignored with a note. A repo with no Quality check line runs nothing.
- It is the only writer of `lib/full_check_receipt.py`'s receipt, kept per work tree under the git dir: a `started` row
  before the check runs, one `step` row per `&&` step (its text, whether it runs tests, its check scope), and a
  `finished` row with the result, the overall exit and the tree fingerprint taken after the run: the `tree:` line
  full_check prints, from `reviewed_tree.work_tree_fingerprint`.
- The verdict is the exit code plus whether the run was whole. The receipt is satisfied when the command exited 0 (or
  there was no command to run), except that an exit 0 whose runner summary reports failures (the long-standing
  `failed (exit 0, summary reports failures)` result) voids it. A run with no summary at all keeps the exit code's
  verdict. Test-count parsing was left out: no count sits on the finished row and no verdict reads a parsed count.
- A receipt is valid only when the latest run finished, it was satisfied, no step that runs tests has scope targeted
  (a step that names files, excludes tests or selects some voids it; a step whose scope cannot be read, such as
  `CI=1 make test` or a make call whose Makefile is missing, or one scored none, does not), its fingerprint equals
  the current tree's (the check's log file left out of both), and HEAD still names the commit HEAD named when the run finished. A
  later run with no finished row voids an older receipt.
- For pytest, a directory-only test path (`pytest tests/`) is a whole run only when it is a pytest `testpaths` entry
  (globs such as `tests/*` expanded to the folders they match); with no `testpaths`, only the top-level `tests` folder
  is the root. A `tests` folder beside set `testpaths` is not a root. `pytest tests/unit` stays targeted.
  `lib/check_scope.py` holds the one rule, so the coder gate refuses `pytest tests/` as a whole-package run. With
  several roots, the paths must name all of them.
- The `Full suite: CI` marker also counts as a heading, in bold or in backticks, in any case.
- The review-loop backstop, handback's ungated deny, the phase-end whole-suite skip in `/code` and verify-prep read the
  receipt. The transcript text scan of full_check.py results and `handback.full_suite_in_ci` are gone.

## Evidence

- The gates decided that a full check ran by matching command text and runner output. A scoped run, an exclude flag and
  a run followed by an edit each passed as a full check.

## Result

- The named test fails before the change (a scoped run that exited 0 wrote no step scope and no receipt verdict from
  it) and passes after it. The receipt tests also cover a scoped, `--ignore`, `-k` or `--deselect` step, a failing step
  and a timeout, each leaving no valid receipt; unparseable or contradictory test output leaving the verdict to the exit
  code and wholeness; an edit, a new untracked file or a later killed run voiding a receipt; the receipt's tree equal to
  the printed `tree:` line; an in-tree log not voiding it; one row per step; steps sharing one shell; a commit after
  a clean-tree run voiding the receipt (`test_a_commit_after_a_clean_tree_run_voids_the_receipt`); a `python -m unittest
  <module>` step leaving no valid receipt, and a make call with a NAME=value argument leaving a valid one. The rule
  that a selection flag with its value attached or a rerun flag reads as a scope has its own test in
  `test_coder_gate.py` (`test_a_selection_flag_with_its_value_attached_and_a_rerun_flag_are_a_scope`). The gate-side
  tests cover the readers: the review-loop backstop, handback's deny, the phase-end whole-suite skip and verify-prep.

## Watch

None: no intake number counts gates passed on a full check that did not cover the tree.

## Back-out

Revert the commit.
