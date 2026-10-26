---
type: "Change"
title: "The review logger saves a dirty reviewed tree as a commit"
description: "A review row logged on a dirty tree now carries snapshot, a commit on HEAD of the tree the gate saw, kept under refs/review-snapshots/<id>, so the frozen review set can use the dirty rows it used to drop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T22:15:23-05:00"}
seq: 23
kind: "fix"
components: ["script/log-review-finding"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_log_review_finding.py::ReviewSnapshotTest::test_a_dirty_tree_is_saved_as_a_commit_on_head_and_the_index_and_working_tree_do_not_change"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `log-review-finding`: on a dirty tree, the logger copies the real index to a temp index, runs `git add -A` and
  `git write-tree` on it, and makes a commit on HEAD with `git commit-tree`. The commit holds untracked files too. It
  is kept under `refs/review-snapshots/<run_id|finding_id>`, and its sha goes on the row as `snapshot`. The user's
  index and working tree are not touched.
- A later row for the same id, such as an ask outcome, sends the commit that the first row saved. LED-48 stores NULL
  for a rewrite that has no `snapshot`.
- A clean tree sends no `snapshot`, because `head` is the reviewed tree.
- Each new snapshot deletes the snapshot refs whose commit is older than 90 days. This happens in the same call, so no
  separate chore runs.
- An older ledger build refuses the whole row with `field_unknown snapshot`. The logger then deletes the ref, sends
  the row again without the field and prints one note. This is the LED-48 D12 gate: a machine without the build,
  such as the work Mac, still logs every row.
- A redirected row with the metrics switch off saves no snapshot, as it writes no row.
- `ledger-write`: with no ledger, `snapshot` is stored as a string, like `head`.
- `tests/scripts/fake_ledger.py`: `FAKE_LEDGER_UNKNOWN_FIELDS` makes it refuse a row the way an older build does.
- agent-evals `bin/build_review_golden.py`: for a dirty finding, the patch head is `snapshot`, so the base is
  HEAD as it was when the review ran. A dirty row with no snapshot is still dropped.

## Evidence

`bin/build_review_golden.py` dropped 687 dirty-tree finding rows and kept 16 to 18 cases
(agent-evals finding `2026-10-25-a-frozen-review-set-from-the-ledger-keeps-18-of`). A dirty row named only HEAD, and
the review loop then changed the reviewed tree in place.

## Result

- On the base scripts, 4 tests in `test_log_review_finding.py` and the snapshot check in `test_ledger_write.py`
  fail. The 2 new `DirtySnapshot` builder tests fail on the base builder, which drops every dirty row.
- A smoke run in a scratch repo, against the real ledger at 9e9b41f with a scratch `AGENT_LEDGER_ROOT`, stored the
  snapshot sha. `git status` was the same before and after.
- The 687 stored dirty rows stay without a snapshot. Only rows logged after this change gain one.
- The builder reads `review-findings.jsonl`, and this machine's rows go to the ledger. A rebuild has to feed it ledger
  rows that carry `snapshot`.

## Watch

None. The next frozen-set build shows the count of dirty rows it kept.

## Back-out

Revert the commit, then delete `refs/review-snapshots/*` with
`git for-each-ref --format='delete %(refname)' refs/review-snapshots/ | git update-ref --stdin` in each repo.
