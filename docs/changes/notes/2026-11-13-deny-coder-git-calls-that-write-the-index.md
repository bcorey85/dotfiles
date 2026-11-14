---
type: "Change"
change_type: "fixed"
title: "Deny coder git calls that write the index"
description: "The git discipline gate now denies the index-writing git calls add, stage, mv, rm, commit, reset, update-index, read-tree, cherry-pick, revert, am, merge, pull, rebase, switch or checkout of a branch with -m, --merge, --conflict, -f or --force (switch also --discard-changes and --orphan), restore --staged, apply --cached/--index/--3way/--intent-to-add and checkout <tree-ish> [--] <paths>, and checkout -p <tree-ish> from a coder, so renames and adds no longer ride into an unrelated commit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T22:56:27-06:00"}
seq: 4
kind: "fix"
components: ["agent/coder", "script/git-discipline-gate"]
evidence: ["test"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::GitDisciplineGateTest::test_coder_index_writes_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

The gate denies git add, stage, mv, rm, commit, reset, update-index, read-tree, cherry-pick, revert, am, merge, pull, rebase, switch or checkout of a branch with -m, --merge, --conflict, -f or --force (switch also --discard-changes and --orphan), restore --staged, apply --cached, apply --index, apply --3way, apply --intent-to-add (and -3, -N) and checkout <tree-ish> [--] <paths>, and checkout -p <tree-ish>, including bundled short flags and abbreviated long options, when the hook payload's agent_type is a coder variant. The main session and other agents are unaffected. The autostash half of rule 1 moved into a check_autostash function called from run(); that refactor changes no behavior.

## Evidence

Tests cover each denied form, the allowed reads, worktree restore, plain `git checkout -- file` and `git checkout branch`, and the main session and other agents.

## Result

A coder that moves files with git mv is told to use plain mv; the gate denies every call listed above from a coder. Merge, pull, rebase and a branch switch or checkout with `-m`, `--merge`, `--conflict`, `-f` or `--force` (switch also `--discard-changes` and `--orphan`) are denied for a coder too; a plain checkout or switch of a branch still passes. A worker session is the main session (no agent_type), so its merges still pass. One is_orphan_option helper reads `--orphan`, its abbreviations and `--orphan=<branch>` for both switch and checkout, so `git checkout --orphan=new main -- f` makes a branch rather than counting as a path checkout.

## Watch

—

## Back-out

Remove the check_coder_index call in run() of git_discipline_gate.py, and delete check_coder_index, writes_index, restore_stages, apply_writes_index, checkout_writes_index, switch_writes_index, checkout_makes_branch, is_orphan_option, checkout_patches, takes_separate_value, merges_on_switch, discards_on_switch and the index constants there. Delete flags_before_value and is_long_prefix from lib/shell_command.py, and the takes_value parameter of without_flag_values, with their tests in tests/scripts/test_shell_command.py and the coder tests in tests/scripts/test_git_discipline_gate.py. Keep is_short_cluster: is_force_push uses it. Keep options_before_separator: check_scope uses it. The check_autostash extraction can stay.
