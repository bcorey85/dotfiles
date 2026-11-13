---
type: "Change"
change_type: "fixed"
title: "Tests isolate the review-gate state root; tests/run.sh fails when the real review-gate folder gains a repo key under the run's temp folder"
description: "The hand-back and review-fix tests run with HOME at a temp folder, and tests/run.sh fails when the real review-gate folder gains a repo key under the run's temp folder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T09:04:24-06:00"}
seq: 1
kind: "fix"
components: ["script/handback", "script/review-fix", "script/run-sh"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_isolated_state.py::IsolatedStateTest::test_the_review_gate_folder_lies_under_the_temp_home_and_the_environment_is_restored"
asked: ""
proof: []
unmeasured: ""
---

## Change

`tests/scripts/isolated_state.py` `isolate_state_root` points HOME at a `tempfile.TemporaryDirectory` cleaned up with
`addCleanup`, and drops `HANDBACK_STORE_DIR`. `test_handback.py` and `test_review_fix_script.py`
call it in `setUp`. `tests/review_gate_unchanged.py` reads the repo keys of each record file in the real review-gate
folder (through `reviewed_tree.read_json_object`) before and after the tests in `tests/run.sh`, which runs the tests with `TMPDIR` set to a
temp folder of its own. It fails with `review-gate-state` and names the file and key of each new key under that
folder; live sessions and other suite runs that change, prune or add files with other keys pass.

## Evidence

judgment: a full suite run rewrote `sess-1.reviewed`, `sess-1.reviewed-base` and the shared `reviewed-trees.json` in
the live `~/.claude/state/review-gate`, so the commit gate's shared record filled with test trees.

## Result

The new test fails on the old tree (no helper) and passes. The full suite passes (3781 tests, 0 failed), and the new check found no new repo key under the run's temp folder in the real review-gate folder.

## Watch

None: the suite check fails loudly on any new repo key under the run's temp folder in the review-gate folder. It does not
check the hand-back store, and it passes a live session's own writes (other keys, pruned or changed files) or a new key
for a repo outside the run's temp folder.

## Back-out

Revert the commit.
