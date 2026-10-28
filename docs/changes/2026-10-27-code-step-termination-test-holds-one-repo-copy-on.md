---
type: "Change"
title: "code-step termination test holds one repo copy on disk at a time"
description: "The termination walk kept an unpacked repo copy per visited node under /tmp and left them behind when it stopped. Each node now keeps a compressed snapshot and its saved state in memory; a copy is unpacked only to step a child or check its commands, and is removed when that step ends."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T21:42:03-05:00"}
seq: 119
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_termination.py::TerminationTest::test_a_walk_stopped_at_its_budget_leaves_no_node_copy_on_disk"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `tests/scripts/test_code_step_termination.py`: each node holds a gzip tar snapshot of its repo and its saved state,
  not an unpacked directory. Reading a node's children uses the saved state in memory. Stepping a child or checking its
  named commands unpacks the snapshot into a fresh directory, removed when that step returns. `register` removes a
  filed node's copy in a `finally`.
- New `TERMINATION_NODE_DUMP` env var writes the visited node ids, so two walks can be compared.
- The temp root is named `termination-<pid>-*`. At start the file removes any `termination-<pid>-*` tree whose pid is
  dead and that has gone untouched longer than the runner's per-file timeout, which covers a run killed by the runner's
  timeout; trees of live pids and trees with no pid stay.
  SIGTERM removes the temp tree and ends the run with the signal.
- Closes the queue items test-code-step-termination-leaks-a-tmp-tree-of and
  test-code-step-termination-unpacks-a-whole-repo. Keeping the saved state in memory gave no speed gain (878 s against
  825 s and 890 s); the unpacks item closes because its "Done when" list is met.

## Evidence

- A walk stopped at a budget of 20 left 19 node copies on disk; a walk of 21 nodes held 21 copies at its peak. Both new
  tests fail before the change.
- `test_the_sweep_removes_only_the_tmp_trees_of_dead_runs` checks the sweep removes the stale tree of a dead pid and
  keeps a recently touched dead-pid tree, live-pid trees and pid-less trees.
  `test_sigterm_removes_the_tmp_tree_and_ends_the_run_with_the_signal` starts the module in a child, sends
  it SIGTERM, and checks the child exits with that signal and its temp tree is gone.

## Result

- Peak snapshot memory is 19.8 MB. Disk holds one node copy at a time, and none after the walk stops.
- The main walk: 878 s after the change, 825 s and 890 s before, all under load. No speed gain.
- Old and new walks both stop at the 5001-node budget with 0 failures. With SHAs, run ids and epochs masked, both visit
  the same 1366 node ids. Path counts differ: 23122 before, 19707 after. The gap is not proven to be noise from the
  masked values.

## Watch

—

## Back-out

Revert the commit. The walk leaves one repo copy per node under /tmp again.
