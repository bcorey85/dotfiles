---
type: "Change"
change_type: "fixed"
title: "close-branch records the reviewed tree in a scratch index and leaves the user's index alone"
description: "close-branch no longer runs `git add -A`: `fix_diff.py mark` records the reviewed tree from a scratch index, and `fix_diff.py show` prints the fix diff command and its files."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-18T00:17:26-06:00"}
seq: 3
kind: "fix"
components: ["script/worktree-snapshot", "script/fix-diff", "skill/close-branch"]
evidence: ["close-branch-stages-every-file-with-git-add-a"]
watches: []
test: "tests/scripts/test_fix_diff.py::FixDiffTest::test_show_lists_only_what_changed_after_mark_and_the_index_stays_as_it_was"
asked: ""
proof: []
unmeasured: "close-branch SKILL.md Steps 3 and 4 now name `fix_diff.py mark` and `show` in place of `git add -A` and `git diff`. No rule-meter run: the steps call a script, and the test checks the index is unchanged."
---

## Change

`lib/worktree_snapshot.work_tree_tree(repo)` builds the work tree's tree object in a scratch index seeded from a copy
of the real index. The new `skills/close-branch/scripts/fix_diff.py` has `mark` (writes the tree id to
`<git dir>/close-branch/reviewed-tree`) and `show` (JSON with `reviewed_tree`, `fixed_tree`, `diff_command`, `files`;
exit 2 with no mark). close-branch Steps 3 and 4 use them in place of `git add -A`.

## Evidence

Every close pass staged every file, so "staged" no longer meant "read by the user", against the global index rule.

## Result

Six tests in `tests/scripts/test_fix_diff.py` and five in `tests/scripts/test_worktree_snapshot.py`. The index
(`git diff --cached --name-only`) is the same before and after `mark` and `show`.

## Watch

None.

## Back-out

Revert the commit.
