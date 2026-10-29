---
type: "Change"
change_type: "fixed"
title: "git-discipline-gate reads git calls in command position and blocks autostash"
description: "The gate parses each git call past git's own options and wrapper words, blocks stash in every form but list and show, blocks autostash on pull, rebase and merge, and lets git words inside heredocs, quotes and comments pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T18:00:00-05:00"}
seq: 170
kind: "fix"
components: ["script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::GitDisciplineGateTest::test_autostash_on_pull_rebase_and_merge_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The stash, amend, worktree-branch and main-branch rules read git calls through `shell_statements` and
  `shell_command`: past `-C <dir>`, `-c <key=value>`, `--no-pager`, env and timeout, inside `$(...)` and backticks,
  and across a backslash-newline. Heredoc bodies, quoted strings and comments are text. A command that names a code
  runner (`bash -c`, eval) is read as text, so every `git` word in it starts a call.
- Stash is blocked in every form but list and show. The message names the tagged push and points to a WIP commit.
- Autostash is blocked: `--autostash` on pull, rebase and merge (the last of `--autostash` / `--no-autostash` wins),
  `-c rebase.autoStash` / `merge.autoStash` turned on, and `git config` setting either key on.

## Evidence

- The old gate let a stash push through when a git option came before `stash`, and let every autostash form through.
- The old gate denied queue items whose heredoc body quoted a stash command.
- The new tests fail on the old gate.

## Result

- A stash or autostash that would reset staged files is denied in every form a session can write; text that only
  mentions one passes.

## Watch

—

## Back-out

Revert the commit.
