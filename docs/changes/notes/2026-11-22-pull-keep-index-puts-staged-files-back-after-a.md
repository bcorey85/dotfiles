---
type: "Change"
change_type: "changed"
title: "pull_keep_index puts staged files back after a pull that changes the built change-log pages"
description: "A pull that changes the built change-log pages and a file the user also staged no longer leaves the tree with none of the local changes."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T14:55:21-06:00"}
seq: 22
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_built_page_clash_beside_an_ordinary_file_the_pull_changed_in_other_hunks_is_rebuilt"
asked: ""
proof: []
unmeasured: ""
---

## Change
The pull-then-put-back script now puts every local change back when the staged files clash with the pull on built pages and also share an ordinary file the pull changed in other hunks. Before, such a pull left a clean tree and a printed `--put-back` that failed the same way. After, staged files return staged, unstaged files unstaged and the built pages are rebuilt by their driver, in one run. `--put-back` takes the same route, and `--help` and `-h` print the usage from any folder.

## Evidence
Reproduced in a throwaway bare origin and two clones with the real change-log builder and merge driver: the old script exited 1 with a clean tree, the new one exits 0 with staged and unstaged state intact. Tests: the pull case, the `--put-back` case (`test_put_back_of_a_built_page_clash_beside_a_mergeable_file_rebuilds_the_page`) and `test_help_prints_the_usage_and_exits_0_from_any_folder` fail on the old script and pass on the new one.

## Result
See Evidence.

## Watch
No intake number reads this script.

## Back-out
Revert the commit.

