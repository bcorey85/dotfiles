---
type: "Change"
change_type: "fixed"
title: "verify-prep gives plan-verifier an output folder and falls back to origin/HEAD for the base"
description: "Plan-verifier now has a named folder inside the checkout's git dir for command output, and verify-prep finds the base on a repo whose default branch is not main or master."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T19:20:52-06:00"}
seq: 6
kind: "fix"
components: ["agent/plan-verifier", "skill/verify-branch"]
evidence: ["session report"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_the_verifier_gets_an_empty_output_folder_in_the_git_dir_and_no_tmp_writes, tests/scripts/test_verify_branch_script.py::PrepTest::test_a_repo_with_no_main_or_master_falls_back_to_the_remote_default_branch, tests/scripts/test_verify_branch_script.py::PrepTest::test_no_main_master_or_origin_head_exits_2_naming_origin_head_and_the_base_flag"
asked: ""
proof: []
unmeasured: ""
---

## Change

verify-prep now empties and creates `<git dir>/verify-output` on each run. The plan-verifier run rules name that folder as the only place for redirected command output, and they forbid /tmp and every other folder. The git dir keeps the files out of `git status`, the diff and the tree fingerprint, so the output never makes a logged review stale. Each prep run empties the folder, so no run's output outlives the next one.

`verify_common.find_base` now tries the remote's default branch (`origin/HEAD`) after origin/master, origin/main, master and main. When none of them resolve, it exits 2, says origin/HEAD is not set, and tells the user to pass `--base <ref>`.

## Evidence

A /code Verify phase on a work repo reported two things:

- plan-verifier redirected command output to /tmp files and left them behind, although its run rules said to create no file;
- verify-prep found no base on a repo with no main or master ref, so the base had to be passed by hand.

The old rule forbade every file but named no allowed place, so the agent fell back to the session habit of writing long output under /tmp. The fix gives the agent a named place instead of adding a stronger ban.

## Result

The three tests fail on the old scripts and pass on the new ones.

## Watch

—

## Back-out

Revert `find_base`, `fresh_verifier_output_dir` and the run-rule text in `verify-prep`.
