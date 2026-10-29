---
type: "Change"
change_type: "fixed"
title: "herdr-worktree takes the fork brief as a file, so a worktree session can fork"
description: "herdr-worktree --fork takes --prompt-file <path>, and the orchestration rule runs it with literal paths in place of --prompt \"$(cat <brief file>)\", which Claude Code's worktree guard refuses."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T14:52:45-05:00"}
seq: 111
kind: "fix"
components: ["script/herdr-worktree", "rule/orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrWorktreeTest::test_a_fork_from_a_linked_worktree_starts_the_forked_session_on_the_prompt_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `herdr-worktree` takes `--prompt-file <path>`: it reads the brief from the file and passes it on as `--prompt` did.
  `--prompt <text>` stays; giving both stops with an error.
- The orchestration rule's worktree bullet runs `herdr-worktree --fork --prompt-file <brief file> <branch>` with literal
  paths, from the main checkout or a linked worktree.

## Evidence

- A session in a linked worktree followed the rule. Claude Code's worktree guard refused
  `--prompt "$(cat <brief file>)"` because a runtime value cannot be shown not to be git. The retry with literal text
  hit herdr's `linked_worktree_source` refusal, which `herdr-worktree` already avoids by handing herdr the main checkout.
- The new test forks from a linked worktree with `--prompt-file` and checks that herdr-dev gets the file's brief. It
  fails on the old script with `unknown option: --prompt-file`.

## Result

- A session in a linked worktree forks a new worktree with one command that holds no command substitution.

## Watch

—

## Back-out

Revert the commit.
