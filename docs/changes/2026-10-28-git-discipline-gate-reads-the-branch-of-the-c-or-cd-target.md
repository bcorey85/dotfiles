---
type: "Change"
title: "git-discipline-gate reads the branch of the -C or cd target"
description: "The commit-on-main and worktree-prefix rules now read the branch of the repo each git call runs in: its -C directory, taken relative to the target of an earlier cd in the same command, else to the cwd. A cd after a ( not preceded by $ and a quoted or variable target are not followed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T21:30:00-05:00"}
seq: 219
kind: "fix"
components: ["script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::GitDisciplineGateTest::test_commit_rules_read_the_branch_of_the_c_or_cd_target"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/scripts/gates/git_discipline_gate.py`: each `GitCall` carries the directory it runs in. `git -C <dir>` and an earlier `cd <dir>` statement move it; a quoted, variable or substituted target leaves it unchanged.
- Rules 4 and 5 run per commit or push call, on `current_branch(call.directory)`. The direct-edit exemption reads `CLAUDE.md` at the target repo's root, not `./CLAUDE.md`.
- `lib/shell_command.py`: `GIT_VALUE_OPTIONS` moves here from the gate and gains `--attr-source`, and the new `git_options` reads git's own options with it, so `git --attr-source HEAD commit` reads `commit` as the subcommand.
- Each `$(...)` or backtick span, and each git call in a code runner's text, starts from the directory the `cd` statements before its own offset resolve to. A `cd` after it does not move it.
- Limits: a command with a `cd` after a `(` not preceded by `$` follows no `cd`; `SUBSHELL_CD` matches such a `(` before a `cd`, quoted or not. A quoted, variable or substituted `-C` or `cd` target is not read, so from a feature cwd `git -C "$REPO" commit` or `cd $REPO && git commit` aimed at main passes. Those calls run from the directory the earlier calls resolved to (the cwd when none did), with the `-C` directory joined to it. A `cd -` is not followed either (OLDPWD is not known). `cd -L|-P|-e|-@|-- <dir>` follows `<dir>` and a bare `cd` follows to the home directory. A `$(...)` or backtick span inside single quotes is still read as a call.
- Closes the queue item git-discipline-gate-commit-on-main-check-ignores.

## Evidence

- From a main checkout, `git -C <feature worktree> commit` was denied as a commit on main. From a feature cwd, `git -C <main checkout> commit` passed.

## Result

- 14 new tests; all 31 gate tests pass.
- On the base gate, `test_commit_rules_read_the_branch_of_the_c_or_cd_target`, `test_a_subdirectory_of_a_direct_edit_repo_is_exempt`, `test_direct_edit_repo_is_read_from_the_target_repo`, `test_an_unreadable_target_falls_back_to_the_cwd`, `test_a_substitution_after_a_cd_runs_in_the_cd_target`, `test_a_command_substitution_keeps_cd_tracking_on`, `test_a_git_value_option_before_the_subcommand_keeps_the_commit_rules`, `test_a_cd_before_a_code_runner_moves_the_text_calls`, `test_a_cd_option_is_skipped_and_cd_dash_is_not_followed`, `test_a_bare_cd_follows_to_home` and `test_a_span_is_placed_by_its_offset_not_by_a_text_search` fail or error.
- `test_a_cd_in_a_subshell_does_not_carry_to_later_statements`, `test_a_call_before_a_later_cd_runs_in_the_earlier_directory` and `test_a_cd_inside_a_nested_substitution_does_not_leak_to_outer_statements` pass on the base gate, which reads the cwd for every call. They pin that this change keeps those cases on the cwd.

## Watch

—

## Back-out

Revert the commit. The gate then reads the cwd's branch for every call again.
