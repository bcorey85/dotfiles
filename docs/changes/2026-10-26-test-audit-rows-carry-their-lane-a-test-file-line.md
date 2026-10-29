---
type: "Change"
change_type: "changed"
title: "Test-audit rows carry their lane, a test file:line or unlocated, and a measured diff size"
description: "A /fix started by a test audit passes lane test-audit to its review-loop, whose metrics and run rows now carry it; log-review-finding measures diff_loc from diff_base=<ref> to the working tree, takes file=unlocated, and refuses a test-intent-reviewer finding with no file or line 0."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T21:08:38-05:00"}
seq: 70
kind: "fix"
components: ["skill/test-audit", "skill/fix", "agent/review-loop", "script/review-loop-gate", "script/log-review-finding"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::RunRowTest::test_a_fix_loop_dispatched_from_a_test_audit_writes_its_run_rows_under_the_test_audit_lane"
asked: ""
proof: []
unmeasured: ""
---

## Change

- /test-audit sends its findings to /fix with `lane: test-audit`. /fix passes a lane its args name to the review-loop,
  and the loop's input list names `test-audit`. `review_loop_gate.py` reads `lane: test-audit` from the loop prompt,
  where it read `none` before, so the loop's run rows carry the lane.
- `log-review-finding` takes `diff_base=<ref>` on a run row in place of `diff_loc=`. It measures insertions plus
  deletions from the merge-base of the ref and HEAD to the working tree, untracked files included, through a temp
  index; the user's index is not touched. It refuses `diff_base` with `diff_loc`, on a finding row, or with no
  merge-base. The temp-index tree build is shared with the snapshot code.
- `log-review-finding` takes `file=unlocated` for a finding that names no file and sends the row with no file and no
  line. A `gate=test-intent-reviewer` finding row with no file, or with a file and no line above 0, is refused.
- /test-audit's logging section says to pass `diff_base`, the test file:line the finding names, or `file=unlocated`.
  `finding-log.md` lists both forms.

## Evidence

- A /code closing-phase test audit logged its fix loop with lane none, most finding rows with line 0 and a guessed
  source file, and a diff_loc typed from `git diff --shortstat HEAD~1`, which covered neither the branch nor the
  audit's uncommitted fixes.
- The lane test fails on the base commit's gate (`'test-audit' != 'none'`) and passes after. Seven new
  `test_log_review_finding.py::TestAuditRowTest` cases cover the measured diff_loc, its refusals and the file/line
  rules.

## Result

- Full dotfiles suite (2355 tests) and ruff pass. `log-review-check` against the live ledger fails its first three
  query cases with "cache busy" on a fresh ledger root; the cases send no new field.

## Watch

—

## Back-out

Revert the commit.
