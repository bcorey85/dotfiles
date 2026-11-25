# Toolkit scripts

Each fact below has one owner. Import it. Never add a second copy of the fact, its regex or its table.

## Search first

Before you add a parser, rule, status, store or classifier, run `rg` for the fact's name and its words (for example `clean`, `fingerprint`, `test_path`, `scope`). When an owner exists, import it. When it lacks what you need, extend the owner.

## Owners

- Review converged or clean status: `review/handback.py` `CLEAN_STATUSES` and `false_clean_reason`, and `review/capped_review.py` `effective_status` (a capped packet reads as `deferred` only with no blocker, no open class, no unrun scoped reviewer and a passed full check of the final tree). Read it; never re-derive it from packet text, a transcript or a session line.
- Converged-review credit, the reviewed tree and the push check's read of it (`push_review_state`): `lib/reviewed_tree.py` (`record_reviewed`, `is_reviewed`, `reviewed_fingerprint`, which leaves out the notes paths of `lib/notes_paths.py`); the writers of the record are `handback.record_clean_review`, fed the dispatch repo from the store, and `review/verify-log review`, which credits the tree it logged. Fingerprint the repo that was reviewed, never the hook's cwd.
- Tree identity: `lib/reviewed_tree.py` `tree_fingerprint` (`work_tree_fingerprint` for the work tree against its HEAD). Never hash a tree another way. The git tree object id of the work tree, which is not a fingerprint: `lib/worktree_snapshot.py` `work_tree_tree`. A review diff's base with merged-in commits left out: `lib/merge_free_base.py` `merge_free_base`.
- Hand-back rows (dispatch, hand-back, stop, step): `review/handback_store.py`.
- Review loop parts, as `LoopRun` mixins: a reviewer's findings taken in, `review/review_loop_intake.py`; the read of the last fix pass and late repairs, `review/review_loop_final_read.py`; a pass checked against later phases and removed lines, `review/review_loop_pass_checks.py`; files the user ruled out, `review/review_loop_ruled_out.py`; files outside the review's scope that a fix pass changed and the loop puts back, `review/review_loop_scope_guard.py`; the untracked-file guard around each model call, `review/review_loop_untracked.py`. A blocker line's text: `review/review_blocker_text.py`.
- Full-check result and scope: `review/full_check.py` owns the result values. `lib/check_scope.py` owns whether a command is whole or targeted.
- Whether a full check ran on the current tree: `lib/full_check_receipt.py` (`valid_receipt`, `receipt_problem`), written only by `review/full_check.py`. Never match a command's text or a result line to decide it.
- Whether a logged branch review covers the current tree with no open ask: `review/verify_common.py` (`branch_review_covers`), from the saved verify context (`verify-log review` and `verify-log --asks-ruled`).
- Test file and test path: `lib/source_paths.py` (`is_test_path`, `is_runnable_test_file`). The tests a command runs by name, and whether each is still in the tree: `lib/named_test_targets.py`; kept through a fix pass by `review/review_loop_named_tests.py`.
- Test runner output: `lib/test_run_output.py`. Whether a check passed or could not run: `lib/check_output.py`.
- Every question about a command (runs tests, runner family, is a check, test filter, cargo test target): `lib/check_scope.py` (`runs_tests`, `runner_family`, `is_check`, `command_check_scope`, `names_test_filter`, `names_cargo_test_target`, `names_test_runner`, `prints_own_runner_summary`). Add no per-gate runner or flag table.
- Shell command parsing in a gate: `lib/shell_command.py`; whether a step runs, and in what order (`step_may_be_skipped`, `step_runs_in_background`, `runs_only_after_success`, `step_surely_ran`): `lib/shell_steps.py`; cd targets and the folder a step runs in (`cd_folder`, `ShellDirectory`, `DIRECTORY_MOVE_WORDS`): `lib/shell_directory.py`; `$'...'` words: `lib/shell_statements.py` `without_ansi_c_quotes`; quote and comment positions (`quoted_positions`, `unquoted_matches`): `lib/shell_quoting.py`; what zsh expands in a word, redirect target words included: `lib/shell_expansion.py`; which word of a command is its name (`command_word_index`, `raw_word_names_command`): `lib/shell_command_words.py`; the text a gate reads from a command (heredoc bodies and comments cut, split lines joined): `lib/shell_statements.py` `shell_code`. Never use a bare `shlex.split`, `str.split` or operator regex on a command.
- Whether a git call makes a commit, and which folder it lands in: `lib/git_commit_calls.py` (`git_call_commits`, `git_commit_dirs`), with `lib/shell_command.py` `git_c_directory`; through an alias: `lib/git_alias_commits.py`. Never read the hook's cwd alone. Which git calls destroy work or skip a check: `lib/git_destructive_calls.py`, with the subcommand option facts (false config values, protected branch names, `checkout`, `switch` and `restore` option values) in `lib/git_subcommand_options.py`.
- Ask outcome words (`accepted`, `rejected`) and the `phase_asks.py` ruling command: `lib/ask_outcome_words.py`, which imports nothing.
- A lock held across processes: `lib/file_lock.py`. Never write a second flock helper.
- Whether a process id is alive: `lib/process_group.py` `pid_is_alive`. Never call `os.kill(pid, 0)` elsewhere.
- Claude session folders and live session rows (sessions, projects, the config dir override): `lib/session_registry.py` (`sessions_dir`, `projects_dir`, `live_session_rows`).
- Stop file names (`stop.md`, `review-stop.md`): `lib/stop_file_names.py`, which imports nothing. The Write gate loads it on every code-fork Write in a run folder.
- Review-fix state folder and file names, the asks-findings file name, and the `asks_launch_pending`, `correct_open` and `asks_decided_by` keys: `lib/review_fix_names.py`, which imports nothing. `review/review_fix_state.py` re-exports them.
- Text for a changed or no-code ask ruling on a finding (ruler clauses, marker, no-code test): `lib/ruled_change_text.py` (`changed_text`, `ruled_note`, `is_no_code_ruling`), standard library only. The sign-off lines of a decision log: `lib/signoff_lines.py`; a standing ruling's form and reader: `lib/standing_rulings.py`; a coder pass never edits a sign-off line, and a ruled sign-off edit is handed back to the caller: `review/review_loop_signoffs.py`, which puts changed lines back through `lib/protected_lines.py`.
- Uncommitted change of a repo, for a stop that leaves the tree dirty: `review/uncommitted_hunks.py` (`hunk_lines` gives `path:first-last`, `path (changed)`, `path (deleted)` and `path (untracked)` lines, plus a clean line and a not-read line; `stop_lines` puts `Uncommitted: ` in front of them for a cap stop).
- Plan text: `lib/plan_format.py`.
- TOML files: `lib/toml_file.py` `read_toml`. Never import tomllib elsewhere: the scripts run on Python 3.10.
- State file paths and writes: `lib/script_utils.py` (`state_file_path`, `write_text_atomically`, `read_jsonl`).
- How alike two strings are: `lib/script_utils.py` `text_similarity`; two sequences of items: `lib/sequence_similarity.py`.
- Clone detection for /refactor and the duplicate-code gate: `skills/refactor/scripts/clone_pairs.py` (jscpd pairs on changed lines) and `skills/refactor/scripts/shape_clones.py` (function bodies with names and literals stripped). Syntax trees from the tree-sitter CLI: `lib/tree_sitter_xml.py`.
- Exit 2 when a fail-closed gate's import crashes: `lib/import_guard.py` `guard`, which imports nothing of the toolkit.

## Data between steps

- Steps pass JSON to each other. Never render JSON as text for another script to parse.
- Never add a regex or prefix match over another script's output. Add a field to its JSON and read the field.
- A new status or result is a named constant in its owner, and readers compare against it.

## Failures and writes

- Never swallow an exception in a hook. Report it on stderr or in the hook's deny or stop message, and name the gate.
- A gate picks fail-open or fail-closed on purpose, and says which in a comment.
- A command writes its state in one atomic step (`write_text_atomically`), once per run. The review loop's `approval-asks.json` is the exception: it is saved at the start of a run that holds saved asks and each time a fix pass files an ask, so a crash keeps an ask that waits on the user.
- Put tests for a script under `tests/scripts/`, with paths from `tests/scripts/toolkit_paths.py`.
