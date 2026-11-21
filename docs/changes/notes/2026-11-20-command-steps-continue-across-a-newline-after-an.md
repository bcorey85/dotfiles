---
type: "Change"
change_type: "fixed"
title: "Command steps continue across a newline after an operator and read a backslash continuation"
description: "split_command_steps keeps a step going across a newline after &&, || or | (and after a trailing |&), and the gates that read steps join a backslash-newline first."
generated: {"by": "claude-sonnet-5-5/coder", "at": "2026-11-20T21:18:54-06:00"}
seq: 5
kind: "fix"
components: ["script/shell-command", "script/shell-steps", "script/git-discipline-gate", "script/quality-check-cap", "script/rg-path-gate", "script/shell-variables", "script/git-commit-calls", "script/check-scope", "script/inline-interpreter-hint", "script/git-calls", "script/shell-write-gate", "script/review-commit-gate", "script/shell-statements"]
evidence: ["review of the shell gates: `git pull --autostash &&` then a newline then `git push` read as two commands joined by a newline, so the allowed pull-and-push pair was denied, and a `cd` after `&&` and a newline read as unconditional"]
watches: []
test: "tests/scripts/test_shell_command.py::SplitCommandStepsTest::test_a_newline_after_a_list_operator_continues_the_list"
asked: ""
proof: []
unmeasured: ""
---

## Change

`shell_command.split_command_steps` no longer ends a step at a newline that follows `&&`, `||` or `|` (only blanks or a comment between), and a step that ends in `|&` goes on across the newline: the next line continues the list, as the shell reads it. The continued step keeps its leading newline, so `shell_steps.SETUP_STEP` accepts a leading newline, and takes the `cd` word from `shell_directory.CD_WORD`.

Gates that read the steps and so see the new split: `git_discipline_gate` (`git pull --autostash &&` newline `git push` now counts as the allowed pair), `quality_check_cap` (`record_runs`), `rg_path_gate`, `shell_variables`, `git_commit_calls`, `check_scope.step_check_scope` and `inline_interpreter_hint`.

A step after an operator and a newline keeps that newline at its start, so every reader of a step's leading text skips a newline as well as blanks: `shell_steps` (`group_closes`, `step_parts`, the leading and trailing brace patterns) and `git_calls.read_part`. `true &&` newline `(cd /tmp && git commit -m x)` reads like its one-line form, and `ls &&` newline `(cd /x && git commit)` is a conditional cd.

A backslash-newline stays inside its step. These gates remove it (with nothing in its place; `shell_quoting.join_line_continuations`) before they split. An escaped backslash before a newline (`\\`) is no continuation and the line ends there, as does a backslash in single quotes or a comment: `pipe_shell_check` (`pipes_into_shell`), `quality_check_cap`, `rg_path_gate`, `check_scope` (`step_check_scope`), `review_commit_gate`, `git_calls` (`has_conditional_cd`, `git_calls`), `inplace_edit.file_operands`, `git_discipline_gate` (the pull-and-push pair), `inline_interpreter_hint` and `shell_write_gate` (the whole command, before its targets, folders and scripts are read): `ls && \` newline `cd /x` reads as a conditional cd, `ls && \` newline `rg foo` as an `rg` with no path, and for the main session `echo hi | tee \` newline `tracked.txt` and `echo hi > \` newline `tracked.txt` are now denied as a write to a tracked file (before: allowed; for a coder: denied with the target `\`). The gates that read a whole Bash command (all but `check_scope`, `review_commit_gate` and `inplace_edit`, and including `pipe_shell_check`) take their text from `shell_statements.shell_code`, which cuts heredocs and comments before it joins: a `\` ending a comment line is literal in zsh, so `git status # note \` newline `git commit -m x` still reads the commit. `review_commit_gate` (`is_commit_command`, `readable_command`) cuts comments before its join the same way, but only outside heredoc bodies (`shell_statements.outside_heredoc_bodies`, which also bounds its `$'...'` decoding): it keeps each body as written instead of calling `shell_code`. A `#` after a backslash-newline starts a comment when the text before the backslash is a blank (`quoted_positions` reads it so).

Readers that do not join a backslash-newline, so a command split by one is read as written: `shell_variables`, `interpreter_writes.runs_editor`, `shell_statements` (`blank_script_run_quotes`, `pipes_out_of_compound`), `commit_placement`, `shell_command.step_words` and `and_steps` (so `check_scope.and_steps_or_whole`), and `shell_write_gate` code read from a heredoc or script file. No session has hit one; each stays a gap, not a fix.

## Evidence

`test_a_newline_after_a_list_operator_continues_the_list` pins the split. `test_after_failure_a_setup_step_before_a_newline_continuation_does_not_hide_the_next_step` and the quality-check-cap tests for a newline and a backslash-newline continuation fail without the change; the `has_conditional_cd`, `rg` and `step_check_scope` cases with a backslash-newline are pinned in `test_git_calls.py`, `test_rg_path_gate.py` and `test_full_check_receipt.py`.

## Result

The 12002-command replay of real Bash commands (see the computed-target note) was run over the final tree; its verdict changes are listed there.

## Watch

A multi-line command with an operator at a line end whose gate verdict changed: the git-discipline pull-and-push pair, a quality-check-cap record after a failed chained run, and an `rg` or `cd` after a backslash-newline. Each one is the case to review.

## Back-out

Restore the newline split in `split_command_steps` (drop the `continues_list` test) and remove the `join_line_continuations` calls from the readers listed above.
