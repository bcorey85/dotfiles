---
type: "Change"
change_type: "fixed"
title: "The code step and the review loop share one working-tree scan and one size bar"
description: "One lib scan of the working tree against HEAD serves the code step and the review loop, and one owner holds the 40-line structure-pass bar, so a 40-line docs follow-up gets the same small-or-large answer on both sides."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T18:07:11-05:00"}
seq: 284
kind: "fix"
components: ["script/code-step", "script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_change_size_bar.py::ChangeSizeBarTest::test_a_follow_up_that_adds_forty_lines_of_docs_is_small_for_both_sides"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `worktree_snapshot.working_tree_changes(root)` returns `{path: {code, hash, added, deleted, new}}` for the working
  tree against HEAD. `new` is True for an untracked file and one added to the index, intent-to-add included. Hashes are git blob hashes from one `git hash-object` call, so a saved baseline still compares equal.
  An untracked file counts every line, a last line with no newline included.
- `code_step_core.file_hashes`, `code_step_review.change_snapshot`, `code_step_boundary.diff_stat_rows` and
  `review_loop_script.scope` call it behind their current names.
- `source_paths` owns `LARGE_ADDED_LINES` and `counts_toward_size` (counted source, not `.md`). The code step's
  follow-up check and the review loop both use them; `review_loop_script.LARGE_ADDED_LINES` stays importable.
- `source_paths.is_large_change(added_lines, new_paths)` is the one large-change test both callers use: 40 added
  counted lines, or a new counted source file.
- An intent-to-add file is new on both sides. A new non-counted file, such as a lockfile, no longer makes a change
  large in the review loop.
- `diff_stat_rows` shows `+0 -0` for a listed file that is no longer dirty and for a binary file.
- A pure rename counts 0 added lines: the scan keeps git's rename detection and reads a renamed file under its new
  path with only its edited lines, so a renamed 50-line source file is small on both sides.
- The numstat and status reads pass `--find-renames`, so the user's rename config cannot change a count. Numstat is
  read with `-z` (`code_step_concentration` too), and a rename in the work tree column skips its old path like one in
  the index column, so the old path no longer parses as a garbage entry.
- A symlink to a file hashes as its target's bytes, as `git hash-object <path>` printed it before; a symlink to
  nothing has no hash.

## Evidence

- The code step counted `.md` files toward the 40-line bar and the review loop did not, so a follow-up adding 40
  lines of docs was large on one side and small on the other. The code step also counted an untracked file without a
  final newline one line short.

## Result

- The named test and its untracked-file sibling failed before the change and pass after it.
- Source lines went +124/-83, not the roughly 35 fewer the item guessed. The lines were never the aim: the point is
  that both sides now give one answer.

## Watch

None: no intake number reads which side ran the structure pass.

## Back-out

Revert the commit.
