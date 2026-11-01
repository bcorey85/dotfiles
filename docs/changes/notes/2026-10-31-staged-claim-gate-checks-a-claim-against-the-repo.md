---
type: "Change"
change_type: "fixed"
title: "staged-claim gate checks a claim against the repo the message names"
description: "A session that reports a file staged in a sibling worktree, named by folder, by `git -C <folder>` or by a `~/` path, ends its turn when that worktree's index holds the file: the staged-claim gate checks that index instead of the cwd's. A false claim there still blocks, by file name."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T21:01:17-05:00"}
seq: 412
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::StagedClaimGateTest::test_a_claim_naming_another_tree_by_folder_git_dash_c_or_home_checks_that_tree_index"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The gate reads the repos a claim names from each existing absolute path, each `~/` path, and each folder a
  `git -C <folder>` in the sentence runs in, a relative folder read from the cwd.
- A relative file the sentence names is read from the cwd when the repo holds the cwd, else from that repo's top, so
  `a.txt is staged in <other tree>` checks `a.txt` in that tree's index.
- A claim that names no repo still checks the cwd's index, as before.

## Evidence

judgment: a coordinator reported a file staged in a sibling worktree, which was true there, and the gate blocked
its turn because the cwd repo's index was empty.

## Result

The named test fails before and passes after, for five forms: a tree folder, `git -C` with an absolute, a relative
and a `~/` folder, and a `~/` tree folder. Each form blocks with an empty index, blocks naming the file when the
index holds only another file, and passes once the file is staged. A second test keeps a claim that names no repo
on the cwd index while another repo holds the file. Two more keep a tree the session staged in from vouching for a
claim that names another tree, and keep that vouch when a `git -C` folder cannot be read. `test_staged_claim_gate`:
38 tests, 0 failed; ruff clean.

## Watch

None. A wrong block shows in the session that hits it.

## Back-out

Revert `GIT_FOLDER`, the `~/` form of `PATH_WORD`, `path_words`, `named_absolute_paths`, `named_trees`, the base
argument of `named_files`, the change to `sentence_problems`, and the two tests.
