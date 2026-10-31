---
type: "Change"
change_type: "fixed"
title: "Forked herdr session takes its worktree's name"
description: "A session that herdr-worktree --fork opens now starts with the worktree's folder name as its display name, so peers no longer see two sessions under the parent's name."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T09:04:42-05:00"}
seq: 340
kind: "fix"
components: ["script/herdr-dev"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrDevTest::test_the_fork_is_named_for_its_worktree_so_peers_can_tell_it_from_its_parent, tests/scripts/test_herdr_worktree.py::HerdrDevTest::test_a_worktree_folder_with_shell_special_characters_is_typed_as_one_name_argument"
asked: ""
proof: []
unmeasured: ""
---

## Change

- herdr-dev starts a fork with `claude --resume <id> --fork-session --name <worktree folder name>`. The name is
  shell-quoted before it is typed into the pane.

## Evidence

- A forked worktree session kept its parent's peer name. A worker could not tell the two sessions apart and waited
  hours on a message that went to the wrong one.

## Result

Against the script before this change, the new test fails: the fork command carries no `--name`. After it,
`test_herdr_worktree.py` passes (8 tests) and ruff passes.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. A forked session then shows its parent's name again.
