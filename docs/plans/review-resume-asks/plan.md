# Review resume: the fix round runs, named tests run, asks read one way, accepted asks stay accepted

Fix four queue items from /review and /fix resume runs. Each phase starts with a test that fails on the current tree.
Scripts live in `claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

## Scope

- In: `review/review_fix_asks.py`, `review/review_asks.py`, `review/review_fix_state.py`, `review/review_launch.py`,
  `review/review_fix.py` (packet path only; it is 970 lines, so new logic goes in a sibling module),
  `gates/fork_write_scope.py`, the resume and ending paragraphs of `skills/_shared/review-fork-run.md`, and the tests
  of each.
- Out: `review/review_loop_prompts.py`; `review/review_loop_script.py` (over 1000 lines; no new route there); the
  lint, format, gate-env and removed-change code; `agents/coder.md`; `gates/pipe_shell_check.py`;
  `tools/pull_keep_index.py`; the ledger half of `review-loop-skips-requested-scoped-tests-and`.

## Phase Status

- [x] Phase 1: a resumed review cannot stop before the fix run asks-done printed (risk: medium)
- [x] Phase 2: test commands named in a resume reply run in the fix run (risk: low)
- [x] Phase 3: asks-done refuses a conditional proposed change and corrects a logged outcome (risk: medium)
- [ ] Phase 4: a user-accepted ask the fix coder skips comes back as an ask (risk: medium)
- [ ] Phase 5: asks-done needs --by; no default records a user sign-off (risk: low)

## Phase 1: a resumed review cannot stop before the fix run asks-done printed

Bug: a resumed /review applied the user's asks through asks-done, which printed `ACTION: redispatch` and a launch
line, but the fork wrote `review-stop.md` and ended without running it. No review round covered the fix.

1. `review_fix_asks.write_unprinted_fix_run`: when it stores `asks_launch_line`, also set top-level
   `state["asks_launch_pending"] = <the launch line>` (saved in the same `save_fix_state` write).
2. `review_launch.command_launch`: when `--fix` names the pending findings file (`<git dir>/review-fix/
   ask-findings.md`), clear `asks_launch_pending` in that repo's fix state before validation, through
   `review_fix_state`'s load and save, so a launch that fails afterward still lets the fork report the failure.
   A repo with no fix state is untouched.
3. `gates/fork_write_scope.py`: a code-fork Write to `<run folder>/review-stop.md` is denied while
   `<run folder>/../review-fix/state.json` holds `asks_launch_pending`. The run folder's parent is the git dir, so the
   gate needs no git call. The deny names the launch line to run first. The gate stays fail-closed for code-fork, and
   other agents still exit before any file read. Keep `review-fix` and the state name owned by `review_fix_state`
   only if importing it does not slow every Write: when it would, keep the two names as constants in the gate with a
   test that compares them to `review_fix_state`'s.
4. Measure the gate's median time on a matched code-fork Write and on a non-code-fork Write, next to a bare
   `python3 -c pass`, and put the numbers in the phase's hand-back.

#### Automated Verification

- New test in `tests/scripts/test_fork_write_scope.py`: a code-fork Write to `review-stop.md` with a pending launch
  line in the fix state is denied and the reason names the line; with no pending flag it is allowed; a non-code-fork
  Write is allowed either way.
- New tests in the review_fix tests: asks-done that prints a launch line sets the pending flag; a launch with that
  `--fix` file clears it, also when the launch then fails validation.
- `python3 tests/parallel_tests.py test_fork_write_scope.py` and the changed review_fix test files pass.

## Phase 2: test commands named in a resume reply run in the fix run

Bug: the user's resume reply named test commands to run; the run never ran them and said nothing about them.

1. `review_launch.launch_parser`: add `--test CMD` (repeatable, `dest="tests"`). Pass each as `--gate-command CMD` to
   the loop script (which already runs them through `scoped_tests_pass` and reports `scoped_tests` in the packet).
   Keep `--test` flags in `relaunch_args`, so a later fix run carries them.
2. When the loop converges with no untested fix, `scoped_tests_pass` does not run. A launch with `--test` must still
   run them: check in `walk` whether the caller's commands run on every converged run; if they only run when
   `untested_fix` is set, make the launch pass a flag the loop already has, or report "scoped tests not run: <why>"
   in the packet. No new route in `review_loop_script.py`: if a change there is needed, stop and report.
3. `review-fork-run.md` Resume paragraph: test commands named in the reply go on the launch line of the run the reply
   starts, one `--test '<command>'` each; when the reply starts no run, launch the stop's next run with them.
4. The stop text reports the packet's scoped-tests line (pass/fail counts, or why they did not run).

#### Automated Verification

- New test in the review_launch tests: `launch --test 'cmd a' --test 'cmd b'` passes both as `--gate-command` to the
  loop script and stores both in the relaunch args.
- `python3 tests/parallel_tests.py` on the changed test files passes.

## Phase 3: asks-done refuses a conditional proposed change and corrects a logged outcome

Bug: an ask's proposed change was conditional ("if not confirmed, revert X"); the user said yes, asks-done logged
`accepted` and the fix coder applied the revert, the opposite of the user's answer. A second asks-done with the right
outcome printed "already logged" and could not fix it.

1. `review_asks.py`: own one constant pattern for a conditional proposed change: a change is
   conditional only when it hangs on the answer to the ask: it starts with `If not`, `If no`, `Unless` or
   `Otherwise`, or holds `if (not )?(confirmed|approved|accepted)`, `if yes`, `if no,` or `if the user`. One function,
   `is_conditional_change(text)`.
2. `asks-done`: when an `accepted` or `rejected` outcome lands on an ask with a conditional change, refuse before
   logging anything (exit 2). Name the ask and tell the caller to answer it with `modified:<the change to make, with no
   condition>`. A `modified:` outcome is never refused.
3. `asks-done --correct <outcome>...`: allowed only while `asks_launch_pending` is set (Phase 1). It logs a new row
   for each ask whose outcome changes, rewrites `ask-findings.md` from the corrected outcomes, and prints the launch
   line again (no findings left → clears the pending flag and prints `ACTION: done`). With no pending launch it
   refuses and says the fix run already started. First `rg` how `ask_outcome` rows are read (`log-review-finding`,
   `handback.py`, `skills/audit/review.md`, `~/agent-evals/bin/`): if any reader takes the first row of a finding_id
   rather than the last, stop and report before writing this step.
4. The stop and packet render each ask's proposed change with what accepting it does: `Accept = make this change:
   <change>. Reject = leave the code as it is.` Put the wording in one place.

#### Automated Verification

- New tests: asks-done `accepted` on an ask with change "If not confirmed, revert X" exits 2, logs nothing and names
  `modified:`; `modified:revert X` on the same ask logs and writes the finding; `--correct rejected` after an
  `accepted` with the launch still pending rewrites the findings file without the ask and logs the new outcome;
  `--correct` after the launch cleared the flag refuses.
- `python3 tests/parallel_tests.py` on the changed test files passes.

## Phase 4: a user-accepted ask the fix coder skips comes back as an ask

Bug: the user accepted an ask through `/fix resume accept`; the fix run's coder objected and the finding landed in
`skipped_fp`, so the user's decision was dropped without a word.

1. `review_launch`: add `--user-ruled` (needs `--fix`); store `user_ruled: true` in the launch record.
2. `asks-done --by user`: the launch line it prints carries `--user-ruled`.
3. `review_fix.py packet`, through a new sibling module: when the launch record holds `user_ruled`, each `skipped_fp`
   entry becomes an ask whose question is `You accepted this change; the fix coder skipped it: <reason>. Apply it
   anyway?` and whose proposed change is the skipped item's text. It is removed from `skipped_fp`. The packet then
   stops on that ask like any other.

#### Automated Verification

- New test: a packet from a `--user-ruled` launch with one `skipped_fp` entry prints it as an ask with the coder's
  reason and leaves `skipped_fp` empty; the same packet without `user_ruled` keeps the skip.
- Test: asks-done `--by user` prints a launch line with `--user-ruled`; `--by session` does not.
- `python3 tests/parallel_tests.py` on the changed test files passes, then `bash tests/run.sh`.

## Phase 5: asks-done needs --by; no default records a user sign-off

Bug: `review_fix.py asks-done` defaults to `--by user`, so a session's own ruling on a resume was logged with
`ask_decided_by=user`.

1. `review_fix_asks.asks_done_options`: `--by` has no default. A call without it exits 2 before logging anything and
   names both values (`--by user` when the user gave the answer, `--by session` when the session ruled).
2. `rg` every caller of `asks-done` (skills, agents, the opencode ports, and every script that prints an asks-done
   command, such as `review_fix.py asks_done_line`) and make each pass `--by`. A printed command for the session to
   run carries `--by session` unless it relays a user's answer.

#### Automated Verification

- New test: `asks-done accepted` with no `--by` exits 2, logs no row and names `--by user` and `--by session`; with
  `--by session` the row carries `ask_decided_by=session`.
- Every printed asks-done command in the review_fix tests carries `--by`.
- `python3 tests/parallel_tests.py` on the changed test files passes, then `bash tests/run.sh`.

## Plan Deviations

- Phase 1 step 3: the names live in two new import-free modules, `lib/review_fix_names.py` and `lib/stop_file_names.py`, in place of either option the plan gives. One owner holds each name, and the gate imports no heavy module. `review_fix_state` re-exports them. Every acceptance criterion holds.
- Phase 3: the conditional-change pattern is narrowed to wording that hangs on the answer to the ask (starts with `If not`, `If no`, `Unless`, `Otherwise`, or holds `if (not )?(confirmed|approved|accepted)`, `if yes`, `if no,`, `if the user`); plain changes such as "When the list is empty, return []" pass. Session ruling (the /code session, not the user), 2026-11-10.
