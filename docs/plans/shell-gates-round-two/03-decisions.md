# Decisions: fix/shell-gates-round-two

## Ruled: computed-target asks (this lane session, 2026-11-20)

Ruled by the shell-gates-round-two lane session, 2026-11-20 (plain code asks):
1. Temp proof stays per write target, not per argument: a loop that moves listed repo files into a mkdtemp folder is allowed. Known gap, named in the change note; no session hit it, and a removed tracked file shows in git status.
2. One change note per behavior change: add notes for the process-substitution tee read, the `$'...'` reading in the commit gates (with the `<&` and `cd x && y &` changes), and the `strip_comments` escaped-blank fix.
3. An argv script stays denied when any argument is not a temp path, read-only ones included.
4. Accepted limits: a write call inside a string literal of a generator script counts; `.replace(` moves are unchecked. Named in the change note.
5. Done-when item 4 stays: re-run the replay on the final tree and write the numbers and each read verdict change into the change note.
6. (branch review ask) A file listing run through `subprocess` or `os.popen` (`git ls-files`, `git grep -l`, `find`, `ls`) counts as "a directory listing" in the reworded Done-when: a scripted rename lists its files that way, so it is in scope and gets a deny test.
7. (branch review ask, round three) Any `grep` run through `subprocess` or `os.popen` counts as a listing, not only `grep -l`: `grep -r`/`-n` output carries file names a script can split into write targets, so the wider match fails closed. No session hit a false deny from it.

## Ruled: coder-rename-passes-run-regex-scripts-that-can Done-when reworded (agent-evals-5e, 2026-11-20)

Ruled by agent-evals-5e (orchestrating session; criteria owner `session`), 2026-11-20: the item ships as a script fix in place of the coder-brief rule. New Done-when: `lib/interpreter_writes.py` denies a coder's interpreter step (inline code or an untracked script) whose file write target is computed (a glob or directory listing, argv, or a loop over one) with no proof that the path is under a temp dir; the main session's verdicts do not change; the replay of real Bash commands shows each verdict change, and each is read.

## Ruled: `cd` as a bare argument counts as a conditional cd (session, 2026-11-20)

`has_conditional_cd` treats a `cd` that is only an argument (`for f in a; do echo cd; done`) as a real `cd`, so the command's git calls read as the main checkout. Kept: it fails closed, no session has hit it, and the reviewer's case-block-only reading adds code for a designed case. Ruled by this lane session.

## Signed off: Ticket #8 and Ticket #10 overridden (user, 2026-11-21)

Signed off by the user, 2026-11-21, relayed by agent-evals-5e, answering whether Ticket #8 (replay corpus unchanged: 16 shell_write_gate verdicts changed) and Ticket #10 (main session's verdicts do not change: 2 changed) may be logged as overridden, because every change comes from the tee and backslash-newline fixes and each is read in the change notes.

## Applied: scripts/CLAUDE.md `shell_code` Owners clause (agent-evals-5e, 2026-11-21)

Applied by agent-evals-5e, 2026-11-21, at the end of the "Shell command parsing in a gate" line, in the same turn that relayed the user's yes; the ask that drew it listed this clause as pending for the user. Text: "the text a gate reads from a command (heredoc bodies and comments cut, split lines joined): `lib/shell_statements.py` `shell_code`". agent-evals-5e owns confirming the user's yes for this clause.

## Signed off: scripts/CLAUDE.md Owners lines (user, 2026-11-20)

Signed off by the user, 2026-11-20, relayed by agent-evals-5e, answering the ask to add Owners lines for the new helper files from the merged lanes and restore the two git-gates lines they ruled keep (import_guard; git_destructive_calls and git_subcommand_options). Applied in this branch, folded into the matching Owners lines; the named_test_targets / review_loop_named_tests entry was refused by the auto-mode classifier and is not applied.

Applied later the same day by agent-evals-5e on the user's go (2026-11-20), first refused by the classifier in this lane; it is now on the `Test file and test path` Owners line (line 19). No rule-anchors row covers that line. The text:

```
 The tests a command runs by name, and whether each is still in the tree: `lib/named_test_targets.py`; kept through a fix pass by `review/review_loop_named_tests.py`.
```

The shell line as proposed (applied):

```
- Shell command parsing in a gate: `lib/shell_command.py`; whether a step runs, and in what order (`step_may_be_skipped`, `step_runs_in_background`, `runs_only_after_success`, `step_surely_ran`): `lib/shell_steps.py`; cd targets and the folder a step runs in (`cd_folder`, `ShellDirectory`, `DIRECTORY_MOVE_WORDS`): `lib/shell_directory.py`; `$'...'` words: `lib/shell_statements.py` `without_ansi_c_quotes`; quote and comment positions (`quoted_positions`, `unquoted_matches`): `lib/shell_quoting.py`; what zsh expands in a word, redirect target words included: `lib/shell_expansion.py`; which word of a command is its name (`command_word_index`, `raw_word_names_command`): `lib/shell_command_words.py`. Never use a bare `shlex.split`, `str.split` or operator regex on a command.
```
