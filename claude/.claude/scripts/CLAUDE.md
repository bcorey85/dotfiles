# Toolkit scripts

Each fact below has one owner. Import it. Never add a second copy of the fact, its regex or its table.

## Search first

Before you add a parser, rule, status, store or classifier, run `rg` for the fact's name and its words (for example `clean`, `fingerprint`, `test_path`, `scope`). When an owner exists, import it. When it lacks what you need, extend the owner.

## Owners

- Review converged or clean status: `review/handback.py` `CLEAN_STATUSES` and `false_clean_reason`. Read it; never re-derive it from packet text, a transcript or a session line.
- Commit credit and the reviewed tree: `lib/reviewed_tree.py` (`record_reviewed`, `is_reviewed`); the only writer of the record is `handback.record_clean_review`, fed the dispatch repo from the store. Fingerprint the repo that was reviewed, never the hook's cwd.
- Tree identity: `lib/reviewed_tree.py` `tree_fingerprint`. Never hash a tree another way.
- Hand-back rows (dispatch, hand-back, stop, step): `review/handback_store.py`.
- Full-check result and scope: `review/full_check.py` owns the result values. `lib/check_scope.py` owns whether a command is whole or targeted.
- Test file and test path: `lib/source_paths.py` (`is_test_path`, `is_runnable_test_file`).
- Whether a command runs tests, and test runner output: `lib/test_run_output.py`. Whether a check passed or could not run: `lib/check_output.py`.
- Check command classification: `lib/check_scope.py` `command_check_scope`. Add no per-gate runner or flag table.
- Shell command parsing in a gate: `lib/shell_command.py`. Never use a bare `shlex.split`, `str.split` or operator regex on a command.
- Plan text: `lib/plan_format.py`.
- State file paths and writes: `lib/script_utils.py` (`state_file_path`, `write_text_atomically`, `read_jsonl`).

## Data between steps

- Steps pass JSON to each other. Never render JSON as text for another script to parse.
- Never add a regex or prefix match over another script's output. Add a field to its JSON and read the field.
- A new status or result is a named constant in its owner, and readers compare against it.

## Failures and writes

- Never swallow an exception in a hook. Report it on stderr or in the hook's deny or stop message, and name the gate.
- A gate picks fail-open or fail-closed on purpose, and says which in a comment.
- A command writes its state in one atomic step (`write_text_atomically`), once per run.
- Put tests for a script under `tests/scripts/`, with paths from `tests/scripts/toolkit_paths.py`.
