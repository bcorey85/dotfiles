---
type: "Change"
change_type: "fixed"
title: "pull_keep_index docstrings match the exits; replay case cites its queue item"
description: "The module docstring limits the branch-lookup exit to before the pull, exit_upstream_gone gets a docstring, and the gate-replay OR case names the queue item it came from."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T22:41:26-06:00"}
seq: 9
kind: "fix"
components: ["script/pull-keep-index", "script/pipe-shell-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_folder_that_is_not_a_repo_exits_1_naming_the_failed_branch_lookup"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/tools/pull_keep_index.py`: the module docstring says a failed branch-name lookup exits 1 naming the command
only before the pull; after a failed pull it ends in the pull-failure exit. `exit_upstream_gone` gets a one-line
docstring. `tests/scripts/gate_replay_corpus.json` `psc-or-operator-before-shell-script` cites
`queue/pipe-shell-check-flags-bash-command-substitution`, the item the case came from. No behavior change.

## Evidence

judgment: the final branch review found the unconditional docstring claim and the wrong queue citation.

## Result

The gate replay and pull_keep_index tests pass unchanged.

## Watch

None: docs and fixture metadata only.

## Back-out

Revert the commit.
