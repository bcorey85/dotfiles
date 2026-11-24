---
type: "Change"
change_type: "fixed"
title: "pull_keep_index keeps a named ref for the saved changes and prints --help"
description: "pull_keep_index keeps the set-aside changes under a named ref until they are put back, and prints its usage for --help."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T17:41:22-06:00"}
seq: 25
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["tests", "manual run"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_failed_put_back_leaves_a_ref_at_the_saved_commit_and_names_it"
asked: ""
proof: []
unmeasured: "No count shows how often a failed put-back left the edits only in an unreferenced commit."
---

## Change

- `pull_keep_index` makes a ref `refs/pull-keep-index/<UTC stamp>-<saved hash prefix>` for the saved commit before it
  resets the tree. A failed ref write exits 1 naming the saved commit before anything is set aside.
- A successful put-back deletes its ref and lists any older refs under the prefix on stderr, without deleting them.
  `--put-back` takes a ref or a hash and always leaves a named ref when it fails.
- `--help` and `-h` print the script docstring and exit 0.

## Evidence

- `python3 tests/parallel_tests.py test_pull_keep_index.py`: pass.
- `bash tests/lint.sh claude/.claude/scripts/tools/pull_keep_index.py`: pass.
- Manual run: `python3 claude/.claude/scripts/tools/pull_keep_index.py --help` printed the docstring and exited 0.

## Result

Applied. A failed put-back leaves the edits under a named ref, and `--help` prints usage.

## Watch

None: see `unmeasured`.

## Back-out

Revert the commit.
