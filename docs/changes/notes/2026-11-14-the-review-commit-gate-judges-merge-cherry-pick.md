---
type: "Change"
change_type: "fixed"
title: "The review commit gate judges merge, cherry-pick, revert, am, rebase --continue and commit aliases as commits"
description: "A /code phase with unreviewed coder work or unruled reviewer questions can no longer commit through git merge, cherry-pick, revert, am, rebase --continue or --skip or a git alias that expands to a commit; the gate denies each where it denies git commit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-14T23:29:34-06:00"}
seq: 3
kind: "fix"
components: ["script/review-commit-gate", "script/shell-command"]
evidence: ["commit-gate-passes-merge-rebase-cherry-pick-revert"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_call_that_makes_a_commit_is_denied_where_a_commit_is_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `lib/git_commit_calls.py` `git_call_commits`: a git call that makes a commit by itself, namely `commit`, `merge`, `cherry-pick`, `revert` and `am` and `rebase --continue` or `--skip`. `stopping_flags(subcommand)` is the one list of flags that make a call commit nothing: `--abort` and `--quit` (never for `commit`, whose message may hold any text), a merge's `--no-commit` when it is the last of `COMMIT_FLAGS`, its `--squash` when it is the last of `SQUASH_FLAGS` (with `--no-squash`), or its `--ff-only` when it is the last of `FF_FLAGS`, `-n` or `--no-commit` for cherry-pick and revert, `--show-current-patch` for `am` (`am --skip` commits the rest of the series, as `rebase --skip` does). A merge's text pattern applies the same last-flag rule, so `--no-commit --commit` in a command the gate cannot read still counts as a commit. The gate's text patterns (`COMMITTING_CALL`) use the same list and stop at a quote, so a flag inside a quoted message fails closed. A stop flag given as an option's value (`merge -m --abort`, `am --exclude --abort`) is no stop: `git_call_commits` drops the value of each `VALUE_OPTIONS` option of the subcommand before it matches, and `--abort` or `--quit` stops a call only as its one argument. The text pattern takes a sequence-ending flag only directly after the subcommand, and skips a value option and its value when it looks for `--squash`, `--no-commit` and the like. `merge --ff-only` makes no commit either. `git_commit_calls.git_commit_dirs` takes a required `commit_call(words, directory)` argument, places each such call in its directory and returns `CommitDirs(commit_dirs, unplaced, first_call_words)`, or None when the command cannot be read; the gate's alias trigger uses it too, so `cd` and `pushd` move the repo whose config is read. The alias reading lives in `lib/git_alias_commits.py` and reads the call's own `-c alias.<name>=` option and the words passed to the alias.
- `review_commit_gate.py`: `is_commit_command` also counts those calls (through wrappers such as `env`); `commit_dir` and the asks check place them like a commit. A git alias that expands to one is read from the repo config in the directory the call runs in (`git config --get alias.<name>`, one level of `!` shell alias, four aliases deep); a subcommand outside `PLAIN_GIT_SUBCOMMANDS` and `COMMITTING_SUBCOMMANDS` costs that lookup.
- The hook matcher is unchanged. A push line that runs `pull_keep_index.py` and `git push` holds no such call, and a merge in a session with no review state and no open asks passes.
- `cd $VAR && git commit` was already denied in a session with coder work (the unplaceable folder earns no credit). With only open phase asks and no coder work it is denied too: `git_commit_dirs` appends each commit it cannot place (a `cd` to a folder the shell expands, `env -C`, `--git-dir`) to its `unplaced` list, `commit_gate_denials.commit_asks_denial` reads such a commit in the hook's cwd repo (fail closed), and, when the placed repos draw no deny, the deny tells the session to run `git -C <repo> <subcommand>` on one line naming the repo the call lands in. `CommitReader.placed_commits` counts an unplaced alias commit too, so `cd "$D" && git ci -m x` reaches `check_commit`.
- A commit through a `!` shell alias (`git -c alias.ship='!cd /other && git commit -am x' ship`, or the same alias set in the repo config) runs in the calling directory but may commit anywhere, so `git_words_make_commit` answers `git_commit_calls.UNPLACED_COMMIT` for it: `git_commit_dirs` lists it as unplaced and `commit_dir` returns "" for it, so it earns no credit and is read in the cwd repo for asks.
- A non-interactive continue earns credit: `commit_repo_dirs` drops a leading `NAME=value` word (`GIT_EDITOR=true git rebase --continue`), and `git_c_directory` skips `-c core.editor=` and `-c sequence.editor=` as it skips `-c alias.`. A lost-credit deny names the subcommand the command ran (`git -C <repo> merge`), read from `PlacedCommits.first_call_words`, and falls back to `commit` when the words show none.
- The gate reads the placement once: `on_pre_tool_use` calls `CommitReader.placed_commits` and passes the `PlacedCommits(named_dirs, unplaced, first_call_words)` to `check_commit`; `runs_other_commit_call` was renamed `runs_commit_call` and now covers `commit` too. The gate was 1001 lines; `commit_call`, `commit_dir`, `commit_repo_dirs` and the placement moved to `review/commit_placement.py`, which takes the gate's `is_commit_command` and `readable_command` as constructor arguments and so imports nothing of the gate (the gate is now 975 lines).
- `scripts/CLAUDE.md`: the owner line for commit placement names `lib/git_commit_calls.py` (`git_call_commits`, `git_commit_dirs`), `lib/shell_command.py` `git_c_directory` and `lib/git_alias_commits.py`, in place of `lib/shell_command.py` alone. The user approved the edit on 2026-11-15.

## Evidence

Queue item `commit-gate-passes-merge-rebase-cherry-pick-revert`. Each of these failed before the change, in a session with coder work, all in `tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest`: `test_a_call_that_makes_a_commit_is_denied_where_a_commit_is_denied` (merge, rebase --continue, cherry-pick, revert, am, the `cd $WT && git merge side` form, and a commit or merge whose quoted message holds `--abort`), `test_an_alias_that_expands_to_a_commit_is_denied_where_a_commit_is_denied` (plain, `!`, alias-of-alias, the last `-c alias.<name>=` winning), `test_a_merge_whose_last_mode_flag_commits_is_denied`, `test_an_alias_git_words_cannot_parse_is_denied`, `test_a_merge_meets_the_phase_asks_in_a_session_with_no_review_events`, and `NotesOnlyCommitTest::test_a_merge_is_never_notes_only_while_a_commit_of_the_same_notes_passes`. Passing and unchanged: `test_a_call_that_ends_a_sequence_or_leaves_its_result_uncommitted_passes` (abort, quit, `am --show-current-patch`, `merge --commit --no-commit`), `test_an_alias_chain_past_the_depth_limit_passes` (which also asserts the 4-hop chain is denied), `test_an_alias_that_names_itself_passes_without_hanging`, `test_a_call_option_alias_is_read_by_its_value_and_by_the_subcommand_it_names`, `test_an_alias_that_expands_to_no_commit_passes`, `test_the_users_push_line_that_rebases_inside_its_script_passes`, `test_a_merge_in_a_session_with_no_open_state_passes`. Reading of the calls themselves: `tests/scripts/test_shell_command.py::GitCommitDirsTest::test_each_call_that_makes_a_commit_is_read_in_its_dir_and_a_sequence_end_is_not`, `test_a_commit_message_holding_a_stop_flag_still_commits`, `test_stopping_flags_are_empty_for_commit_and_hold_the_stops_of_the_others`. A stale copy of a lib module in `review/` is caught by `StagedLayoutTest::test_no_module_of_lib_has_a_same_named_copy_in_review`.

Added with the branch review, all in `tests/scripts/`, each failing without its change:
- `test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_call_that_makes_a_commit_is_denied_where_a_commit_is_denied` (now also `merge -m --abort`, `-m --quit`, `-m --squash`, `-m --no-commit`, `am --exclude --abort`, their unquoted text-pattern forms in an unreadable command, and `merge --abort side`) and `test_a_call_that_ends_a_sequence_or_leaves_its_result_uncommitted_passes`.
- `test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_through_a_shell_alias_earns_no_credit_in_the_cwd_repo` and `test_a_shell_alias_commit_is_read_in_the_cwd_repo_for_the_asks_check`.
- `test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_continue_with_an_editor_that_never_opens_earns_the_credit_of_the_cwd_repo` and `test_a_lost_credit_deny_names_the_subcommand_that_was_denied`.
- `test_shell_command.py::GitCommitDirsTest::test_a_stop_flag_given_as_an_options_value_is_a_message_not_a_stop`, `test_abort_and_quit_end_the_sequence_only_as_the_calls_one_argument`, `test_the_text_pattern_ends_the_sequence_only_right_after_the_subcommand_and_skips_option_values`, `test_a_commit_call_that_answers_unplaced_commit_is_listed_unplaced_and_names_no_dir`, `test_each_call_that_makes_a_commit_is_read_in_its_dir_and_a_sequence_end_is_not` and `test_stopping_flags_are_empty_for_commit_and_hold_the_stops_of_the_others`.
- `test_shell_command.py::GitCDirectoryTest::test_an_alias_or_an_editor_config_moves_nothing_and_another_c_is_not_followed`.
- `test_review_commit_gate.py::StagedLayoutTest::test_each_staged_file_is_in_the_real_tree_folder_it_is_staged_to` now lists `commit_placement.py`.

The unplaced-commit tests that were already in `tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest` and still pass: `test_a_commit_in_a_dir_the_gate_cannot_place_is_denied_for_the_hook_cwd_repos_asks`, `test_a_commit_in_a_placed_repo_is_denied_without_the_name_the_repo_advice`, `test_an_alias_commit_the_gate_cannot_place_is_denied_for_the_hook_cwd_repos_asks`, `test_a_cd_to_a_shell_expanded_folder_with_no_open_asks_passes_the_asks_check` and `test_an_alias_commit_the_gate_cannot_place_is_denied_in_a_session_with_coder_work`.

## Result

Median of 40 runs of the gate on a real PreToolUse Bash event in a dirty session, next to a bare `python3 -c pass` start (10.4 ms before, 10.8 ms after, load average about 30 on the after run):

| call | before | after |
| --- | --- | --- |
| `git commit -a -m x` (denied) | 119.5 ms | 105.0 ms |
| `git status` | 74.6 ms | 75.9 ms |
| `git merge --no-edit side` | 76.2 ms (passed) | 107.5 ms (denied) |

The matched call (`git commit`) does not slow down; a merge now takes the same full path as a commit.

## Watch

One alias lookup per alias level (`git config --get alias.<name>`, 3 s timeout, up to 4 levels) runs per git call with a git subcommand outside `PLAIN_GIT_SUBCOMMANDS` and `COMMITTING_SUBCOMMANDS` (`CommitReader.placed_commits`, through `git_commit_dirs`, runs on every command that holds `git`, whatever `is_commit_command` returns). The placement is read once and handed to `check_commit`, so the lookups run in `placed_commits` and again in `commit_repo_dirs` for credit, which reads the command again with its own rules. A `-c alias.<name>=` option on the call costs no lookup. In a command with a program beside git (`gh pr create --body "run git merge"`), the plain-text reading counts `git commit` only; a command with a shell or `eval` (`sh -c "git merge x"`) still counts every committing call in its text.

- Shell and `eval` text (`sh -c "git merge x"`) keeps the `COMMITTING_CALL` text pattern, which reads no config: it counts every committing call it finds (ruled exception).
- `git pull` is not gated: a pull that merges still passes. Queued as `commit-gate-passes-a-git-pull-that-merges`.
- The owner line in `claude/.claude/scripts/CLAUDE.md` still names `lib/shell_command.py` for `git_commit_dirs`, which now lives in `lib/git_commit_calls.py`. The branch leaves it for the user.
- `parallel`, `xargs`, `watch`, `flock` and `find -exec`/`-execdir` that run a committing git call are placed in the shell's directory (moved by the call's own `-C`) for the asks check but earn no credit: `CommitReader.commit_dir` reads git only at `words[0]`, so `commit_repo_dirs` returns [None].

## Back-out

Revert the change: the gate then reads `git commit` only.
