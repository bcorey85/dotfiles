---
type: "Change"
change_type: "fixed"
title: "herdr-worktree --fork fails loudly when the fork never starts"
description: "herdr-dev waits for the new pane's shell prompt and clears the input line before it types the claude command, and keeps the brief file until claude exits cleanly. herdr-worktree --fork then waits for herdr to report a claude agent in that pane; if none shows within the timeout it exits 1 and names the pane and the command to run there."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T12:00:00-05:00"}
seq: 180
kind: "fix"
components: ["script/herdr-worktree", "script/herdr-dev"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrWorktreeTest::test_a_fork_whose_pane_never_shows_claude_exits_non_zero_naming_the_pane_and_its_command"
asked: ""
proof: []
unmeasured: "A start check with unit tests; no intake number counts forks that never started."
---

## Change

- `herdr-dev` types the claude command through `start_in_fresh_pane`: it waits up to 10 s for any output in the pane (`pane wait-output --regex '\S'`), sends `ctrl+u`, then types and submits. The wait is best effort; a prompt that never matches still gets the command.
- The brief's temp file is removed by `&& rm -f` after claude exits 0, not inside the substitution, so a mangled or failed start keeps it.
- `herdr-dev` prints the claude pane's id and the typed command, one per line. `herdr-project-open` discards them.
- `herdr-worktree --fork` pushes the branch, then polls `pane get` on that pane once a second for `agent == "claude"`, up to `HERDR_WORKTREE_FORK_TIMEOUT` seconds (default 30). On a miss it exits 1 with the pane id and the command to run in it.

## Evidence

One fork on 2026-10-27: the claude pane showed `zsh: command not found: leclaude`, the brief file was already deleted, and herdr-worktree exited 0, so the parent session reported a running fork.

Tests in `tests/scripts/test_herdr_worktree.py` that fail before the change:
- `test_a_fork_whose_pane_never_shows_claude_exits_non_zero_naming_the_pane_and_its_command`
- `test_the_claude_command_is_typed_after_the_shell_prompt_shows_and_the_input_line_is_cleared`
- `test_the_prompt_file_is_removed_only_after_claude_succeeds_and_both_go_to_stdout`

## Result

The three tests pass, and the existing herdr-worktree tests still pass.

## Watch

None.

## Back-out

Revert the commit.
