# Review loop behavior: findings keep their own reasons, files and sign-offs survive a run, resume bases hold

Fix ten queue items about what the review loop does with findings, files and sign-offs, and how a /code resume picks
its review base. Each phase starts with a test that fails on the current tree.
Scripts live in `claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.
`review/review_loop_script.py` is 957 lines: put new logic in sibling modules (`review_loop_*.py`) and keep its own
growth to the call sites, so it stays under 1000.

## Scope

- In: `review/review_loop_script.py` (call sites only), `review/review_loop_closure.py`,
  `review/review_loop_prompts.py`, `review/review_loop_held.py`, `review/review_loop_coder.py`,
  `review/review_loop_scoped_tests.py`, `review/review_loop_main.py`, `review/review_loop_prompt_file.py`,
  `review/review_loop_packet.py`, `review/handback.py` (packet rendering of new keys only), `review/review_launch.py`,
  `review/review_fix.py` (`blocker_lines` and `plan_impact_lines` only), `lib/file_backup.py`, `code/phase_start.py`,
  `code/code_review_start.py`, `code/code_wait.py`, new sibling modules, the `/review` and `/code` skill lines that
  name a changed flag, `review/review_user_ruled.py` and `review/review_loop_ruled.py` (Phase 9),
  `lib/plan_format.py` (Phases 6 and 10), `review/review_fix_plan_impacts.py` `present_plan_impacts` and the packet's
  plan-impact kind (Phase 10), and the tests of each.
- Out: `review/review_commit_gate.py`; the asks and ruling code of `review/review_fix.py` (`command_decide`,
  `decide_from_hand_back`, `hand_back_plan_impacts`), `review/review_fix_asks.py`, `review/phase_asks.py`;
  `code/gate_commands.py` and `code/coder_gate.py`
  (call them, never edit them); `lib/check_scope.py`; the global CLAUDE.md.

## Phase Status

- [x] Phase 1: class-closure left_alone objects and full blocker text (risk: low)
- [x] Phase 2: a skip reason comes from its own finding; plan-named tests survive a fix pass (risk: medium)
- [x] Phase 3: untracked files survive every model call, and the call that removed one is named (risk: medium)
- [x] Phase 4: held means a named session holds it; a held correct finding comes back unfixed (risk: medium)
- [x] Phase 5: user-ruled out-of-scope files and deletions (risk: medium)
- [x] Phase 6: sign-off lines in decision logs are never edited (risk: medium)
- [x] Phase 7: the last fix round is tested and read; --file takes a scratchpad brief (risk: medium)
- [x] Phase 8: a /code resume keeps the phase base; code_review_start takes an ancestor base; code_wait never returns an earlier phase's packet (risk: high)
- [x] Phase 9: an adopted plan impact reaches the resume round's fix coder (risk: medium)
- [x] Phase 10: a recorded standing ruling settles the criterion rewords it covers (risk: medium)

## Plan Deviations

- Phase 1 step 2: the full-text file for a blocker over 2000 characters is written to review_fix_dir()/blocker-text/<digest>.txt (the review-fix state folder), not the loop's out folder, because the packet carries no loop folder. Adopted by the session, 2026-11-19; no acceptance criterion changed.
- Phase 6 step 1: the sign-off grammar (`signoff_lines` and its helpers) lives in the new `lib/signoff_lines.py`, not `plan_format.py`, because `plan_format.py` is past 1000 lines (the review loop's design-decision ask, accepted). Ruled by the session, 2026-11-19; no acceptance criterion changed.
- Phase 2 step 4: `named_test_targets.named_targets` reads test paths and node ids that exist at repo/<path>; the bare `test_x.py` word of the `python3 tests/parallel_tests.py test_x.py` runner form is not resolved, because `lib/check_scope.py` is out of scope. Known limitation, no acceptance criterion changed. Ruled by the session, 2026-11-19.
- Phase 2 edited lib/check_scope.py (named_test_targets, NODE_SEPARATOR) although Scope lists it as Out; scripts/CLAUDE.md names check_scope the owner of command questions. Adopted by the session, 2026-11-19. This supersedes the reason given at the Phase 2 step 4 line; the bare test_x.py runner word stays unresolved.
- Phase 7: derived test commands come from gate_commands, not CLAUDE.md text (see the AC 10 wording line). The final read first covered the round-budget coder pass only; AC 11 is now closed: `review_loop_final_read.read_late_repairs` gives the gate, lint, class-closure and stale-prose repair passes after the last read one code-reviewer read of their diff, or, when none of their files is in the review scope, leaves `unreviewed_fix` True and names the pass in `scoped_tests`. Closed by the fix pass, 2026-11-19.
- Phase 8: a merge-tree conflict stops with the merge named, as step 3 says; folding a merge the user already resolved (using the merge commit's own tree) is not built (see the Phase 8 and Phase 3 ruling line).
- Phase 9 step 1: the `PLAN_IMPACT_RULED` row carried no decision, ruler or time, and its only writer (`write_ruling_entry` in `review_fix.py`) is out of this phase's scope. `handback_store.record_ruled_impact` now takes `decision`, `owner` and `ruled_at` and `Rulings.adopted` reads them, but until `write_ruling_entry` passed them a recorded ruling read as keep-the-plan, so no adopted ruling reached the fix coder from a real `decide adopt`. AC 16 is now closed: `write_ruling_entry` passes the decision, owner and ruled-at time, and a test runs a real `decide adopt` into the resume round's fix-coder list. Closed by the fix pass, 2026-11-19; no acceptance criterion changed.
- Phase 9 step 2: the check runs in the fix-first pass (the resume round's fix coder) only; a skipped or no-diff adopted finding stops the run as `critical-blocker` before any reviewer is planned. The adopted marker is carried in the finding's text (`review_user_ruled.adopted_issue`), so no new header key reaches the loop.
- Phase 10 step 1: the standing-ruling reader lives in the new `lib/standing_rulings.py`, not `lib/plan_format.py`, because `plan_format.py` is past 1000 lines; `plan_format.ac_drift_failures` and `spec_ac_failures` take a `rewords_ruled` flag that `code/plan_check.py` sets from it. No acceptance criterion changed.
- Phase 10 step 3: a plan impact is a reword when its block says `kind: reword` and names a criterion id; `review_fix_plan_impacts.present_plan_impacts` takes the plan path as a parameter. `review_fix.py packet` now takes `--plan`, passed by `reviewer_dispatch.packet_command` from the loop's `prompt.txt` header, and the PLAN-IMPACT templates carry `kind:`.
- Phase 10 step 4: done by the session on 2026-11-19 (agent-evals bench-base, queue item `## Rulings`).
- Phase 10: the coder-core and code-reviewer PLAN-IMPACT templates (and the opencode code-reviewer port) carry an optional `kind:` line; an impact block without one is not a reword. No acceptance criterion changed.
- Phase 7 edited code/gate_commands.py (`runner_script_commands`, `derive_gate_commands_for`, `python_commands`) although Scope lists it as Out; the AC 10 derivation lives where the gate commands are derived. Adopted by the session, 2026-11-19. No acceptance criterion changed.
- AC 10 derivation: a repo with no Python test config and a `tests/parallel_tests.py` gets `python3 tests/parallel_tests.py <test file name>` for each changed `tests/scripts/test_*.py` file (`gate_commands.runner_script_commands`), and `check_scope` reads that runner as a test run (`TEST_RUNNER_SCRIPT`: targeted with a file name, whole without). A test runs the derived command in a repo shaped like this one and reads its counts.
- Phase 8 and Phase 3: the merge-tree conflict that stops with the merge named (no fold of a merge the user already resolved) and the dropped `file_backup` total cap are accepted as the plan says. Ruled by session dotfiles-review-loop-behavior at 2026-11-19, per the user's resume feedback.
- AC 10 wording: "the changed-file test commands the repo's CLAUDE.md names" is met by the commands `gate_commands.derive_gate_commands` derives for the changed files, provided they run in this repo and report counts; the loop does not parse CLAUDE.md prose. Ruled by session dotfiles-review-loop-behavior at 2026-11-19 (criteria owner: plan; the queue item's words stay met).
- Phase 10 edited review/review_fix.py outside the plan's scope (the decision-word comparisons in `discuss_commands`, `settle_kept_ruling` and `record_plan_ruling`): the literals "adopt" and "keep" became the `plan_format.ADOPT_DECISION` and `KEEP_DECISION` constants. `command_decide` and `decide_from_hand_back` keep their "discuss" and "keep" literals: the commit-gate lane owns those functions (agent-evals-5e ruling, 2026-11-19). Behavior is unchanged; no acceptance criterion changed.

## Phase 1: class-closure left_alone objects and full blocker text

Bug A: the class-closure reply gave `left_alone` as a list of objects. `repaired_closure_problem` (then `closure_list_problem`) rejected it, the retry
gave the same shape, and `ReplyShapeError` stopped the phase as a critical-blocker after the fixes had landed.
Bug B: `review_fix.blocker_lines` and `plan_impact_lines` cut each blocker at 400 characters, so a lint or test
failure lost its failing line.

1. `review_loop_closure.py`: before `repaired_closure_problem` judges the reply, repair a `left_alone` entry that is an object into
   one string: `"<file>:<line> - <purpose>"` from the keys the object holds (`file`/`path`, `line`, and the first of
   `purpose`/`reason`/`reads`/`why`/`what`; any other keys joined as `key: value`). Repair `open` entries the same
   way only when they are objects with a `file` key. A non-string, non-object entry is still a shape problem. The
   existing single retry stays; the retry note names the string shape.
2. `review_fix.py` `blocker_lines` / `plan_impact_lines`: print each blocker in full (`one_line(..., None)`). When a
   blocker is longer than 2000 characters, print its first 2000 and the path of a file in the loop's out folder that
   holds the full text (write it with `script_utils.write_text_atomically`).

#### Automated Verification

- [ ] **Closure object repair**: a left_alone object with file, line and purpose parses to one "a.py:3 - logs it" string with no retry call - `python3 tests/parallel_tests.py test_review_loop_closure.py`
- [ ] **Full blocker text**: a 1200-character blocker prints whole; a 5000-character one prints a path whose file holds all of it - `python3 tests/parallel_tests.py test_review_fix_script.py`

## Phase 2: a skip reason comes from its own finding; plan-named tests survive a fix pass

Bug A: four findings were recorded in `skipped_fp` with reasons that belong to other findings, though all four were
fixed. The coder prompt tells the coder to report small-item skips "with its reason" but gives no form, so a coder
writes `SKIPPED 2: ...` for small item 2 and `skipped_issues` reads it as issue 2.
Bug B: a fix pass deleted a test the plan runs by name (as a duplicate). The scoped-tests check then failed on that
name and raised a false critical-blocker.

1. `review_loop_prompts.SMALL_ITEMS`: small-item skips use `SKIPPED small <n>: <reason>`. `skipped_issues` never
   reads a `SKIPPED small` line as an issue skip.
2. `skipped_issues`: an issue skip line must name its issue: `SKIPPED <n>: <reason>`. When the line's reason names
   another listed issue by number (`issue <m>`, `#<m>`) as the one it covers ("fixed with issue 1", "same as 3"),
   issue n is recorded fixed, not skipped. Keep one parser: extend `skipped_issues`, add no second regex elsewhere.
3. `mark_round_fixes`: match a reviewer's finding to the round's skipped or open items by equality of the finding
   object (or its text), not `finding.text in item.text`, so a short finding text inside a longer one does not take
   its status.
4. Plan-named tests: before each coder pass, collect the test targets the scoped test commands name (file paths and
   `file::name` node ids, read from the commands the loop already holds; use `lib/check_scope.py` and
   `lib/shell_command.py` to read the words) that exist in the tree. List them in the coder prompt as
   "Tests the plan runs by name; never delete or rename them: ...". After the pass, a listed target that is gone
   (file missing, or its `def <name>` / `fn <name>` / `test(...<name>` absent from the file) gets one repair pass with
   the finding "restore <target>: the last fix pass removed a test the plan runs by name". If it is still gone, the
   blocker says "the fix pass removed plan-named test <target>", not a scoped-test failure. Put this in a new
   `review/review_loop_named_tests.py`.

#### Automated Verification

- [ ] **Skip labels**: a small-item skip records no issue skip; a skip that says it was fixed with issue 1 records issue 3 fixed; a short finding text inside a longer one keeps its own status - `python3 tests/parallel_tests.py test_review_loop_script.py`
- [ ] **Plan-named tests**: a fake coder that deletes a plan-named test function triggers the restore pass; a second deletion yields the named-test blocker - `python3 tests/parallel_tests.py test_review_loop_named_tests.py`

## Phase 3: untracked files survive every model call, and the call that removed one is named

Bug: /review deleted untracked files in a worktree twice in one branch; the lane restored them by hand.
`review_loop_coder.put_back_untracked` restores files only after coder calls, only from an in-memory backup capped
at 256 KB per file and 4 MB in total, and says nothing about which call removed them. Reviewer, disposition and
closure calls are not guarded.

1. Find and name the removing step: read `review_loop_coder.py`, `lib/file_backup.py`, every `claude_call` site in
   the loop and `full_check.py`'s temp-tree code; state the step in the hand-back.
   Finding: the removing step is a model call, not `full_check.py`. Its `remove_worktree` (`git worktree remove
   --force`) deletes only the detached temp tree that `git worktree add --detach HEAD` made, which holds tracked
   files only; the repo's untracked files are never in it. Other runs write in the repo and are not guarded: the check
   command (`full_check.run_check_command`, `shell=True`, `cwd=repo`), the gate commands and the formatters
   (`lib/format_files.py`). A test suite or a formatter that cleans up can delete untracked files. The model calls
   also write in the repo: the `claude -p` calls in `review_loop_calls.claude_call` (coder, reviewer, disposition,
   class-closure, retries) and the `--reviewers main` subagents. A run log does not say which of these removed the
   files, so the logs cannot rule out the check, gate and format commands as the remover. Step 2 guards the model
   calls only.
2. Wrap every model call of the loop (coder, reviewer, disposition, class-closure, and their retries) in one guard:
   take the untracked set (and a backup) before the call; after it, restore each missing untracked file the loop
   did not write, and add a `tool_fault` note naming the call (`call-NN-<role>`) and the paths it removed.
3. `lib/file_backup.py`: back up into the loop's out folder (a copy on disk), so no size cap drops a file. Skip only
   files over 50 MB, and name each skipped file in the tool_fault note as not restorable.

#### Automated Verification

- [ ] **Every call guarded**: a fake reviewer call that deletes an untracked file it did not create ends with the file in place and a tool_fault naming the reviewer call - `python3 tests/parallel_tests.py test_review_loop_coder.py`
- [ ] **No size cap**: a fake coder that deletes a 1 MB untracked file gets it restored from the on-disk backup - `python3 tests/parallel_tests.py test_file_backup.py`

## Phase 4: held means a named session holds it; a held correct finding comes back unfixed

Bug: a test-gap finding was skipped as "the file is held by another session". The file was in the session's own
worktree; no other session wrote to it. `phase_start`'s start record marks every file dirty at the run's start with
the same bytes now as held, with no proof another session holds it. The finding went to `skipped_fp`, which reads as a
false positive.

1. `code_review_start.phase_held_files`: a file from the start record is held only when a live session other than the
   run's own (`lib/session_registry.live_session_rows`, cwd inside the repo, a different `sessionId` from the run's)
   exists. Record the holder as `{"path", "session": <name or id>, "claim": "dirty at the run start, unchanged now;
   live session in <cwd>"}`. With no such session, the file is the run's own and is reviewed. A file an earlier
   phase of the same plan changed and left uncommitted is the run's own and never held. Files the caller names
   with `held files:` keep the claim `"named held by the caller"` and the caller as the session.
2. Carry the holder proof into the loop (`held files:` header stays a path list; add a `held-by:` header with the
   JSON holder rows, parsed in `review_loop_prompt_file.py`).
3. `review_loop_held.skip_held_items`: a held finding goes into a new packet list `held_unfixed` as
   `{"item", "reason": "held by <session>: <claim>"}`, not into `skipped_fp`. A finding on a held file with no holder
   row is not skipped: it is sent to the coder like any other.
4. `review_loop_packet.packet_message` and `handback.py`: add `held_unfixed` to the packet keys and print it as
   "Unfixed, held by another session: ..." in the hand-back. It does not make a clean status unclean.

#### Automated Verification

- [ ] **Held needs a holder**: a start-record dirty file with no other live session is not held; with a fake live row for another session in the repo it is held and carries the holder - `python3 tests/parallel_tests.py test_code_review_start.py`
- [ ] **Held unfixed**: a finding on a held file lands in held_unfixed with the session named, and skipped_fp stays empty - `python3 tests/parallel_tests.py test_review_loop_script.py`

## Phase 5: user-ruled out-of-scope files and deletions

Bug: in a /review fix loop the coder re-applied edits to files the user had ruled out of scope (already reverted to
base), re-added a test for one of them, and deleted an in-scope launcher script the user wanted kept. The ruling was
in the session context but never reached the loop's coder brief.

1. `review_launch.py`: add `--ruled-out <path>` (repeatable): a file the user ruled out of this review. It goes in a
   new prompt header `ruled-out files:` (parsed in `review_loop_prompt_file.py`) and in `relaunch_args`.
2. The loop never reviews a ruled-out file and never sends a finding on one to a coder (it goes to `skipped_fp` with
   the reason "the user ruled the file out of scope"). Every coder prompt lists them under a rule: "The user ruled
   these files out of scope. Never edit, create or delete them: ...". Every reviewer prompt lists them as "out of
   scope by the user's ruling; file no finding on them".
3. After every coder pass: a ruled-out file whose bytes changed is put back to its pre-pass bytes (or removed again
   when it did not exist before), and the loop notes it in `tool_fault`. A file in the diff under review that the
   pass deleted, when no finding of the pass names its deletion (the word `delete` or `remove` with the path), is
   restored from the pre-pass backup and noted. Reuse Phase 3's backup.
4. `skills/review/SKILL.md`: one line in the launch step: pass each file the user ruled out of scope as
   `--ruled-out <path>`.

#### Automated Verification

- [ ] **Ruled-out flag**: the ruled-out flag reaches the prompt header and the relaunch args - `python3 tests/parallel_tests.py test_review_launch.py`
- [ ] **Ruled-out header**: the ruled-out files header parses - `python3 tests/parallel_tests.py test_review_loop_prompt_file.py`
- [ ] **Ruled-out put-back**: a ruled-out file edited by a fake coder is put back; a diff file the fake coder deletes with no finding naming the deletion is restored; one deleted under a finding that names it stays deleted; the coder and reviewer prompts list the ruled-out files - `python3 tests/parallel_tests.py test_review_loop_coder.py`

## Phase 6: sign-off lines in decision logs are never edited

Bug: a reviewer objected to three recorded session rulings in a plan's decision log. The loop's coder deleted the
"Ruled by" lines, replaced the rulings with its own verdict and edited the evidence file and the deviations list to
match. The caller restored them by hand.

1. A sign-off line is a line that `lib/plan_format.py` already reads as a sign-off or ruling (the `Ruled by <who> at
   <when>` entry form and the sign-off mark it uses for criteria), plus the ruling text lines of the same entry. Add
   one function to `plan_format.py`, `signoff_lines(text) -> list[(line number, text)]`, and use it everywhere below.
2. Before dispatch: a finding whose file is a decision log (`03-decisions.md`, the plan's `## Plan Deviations`
   section, an evidence file under the plan folder) and whose line is a sign-off line, or whose text objects to a
   recorded ruling, is not sent to a coder. It goes to the packet's `ask` list with the entry named
   (`<file>:<line>`), for the caller to route.
3. After every coder pass: any sign-off line that changed or vanished in any file is put back from the pre-pass
   backup (the whole file, when only the loop's coder wrote it during the pass), and the loop adds an ask naming the
   entry and the reviewer's objection.

#### Automated Verification

- [ ] **Sign-off lines found**: signoff_lines finds every entry form in the repo's own plans - `python3 tests/parallel_tests.py test_plan_format.py`
- [ ] **Sign-offs kept**: a finding on a Ruled by line goes to ask, not the coder; a fake coder that deletes a Ruled by line gets the file put back and an ask is filed - `python3 tests/parallel_tests.py test_review_loop_script.py`

## Phase 7: the last fix round is tested and read; --file takes a scratchpad brief

Bug A: three /review runs ended "Scoped tests: not run (no scoped test commands)" though the coder changed test and
source files; the caller reran the changed-file tests by hand each time.
Bug B: each run ended "Last fix not reviewed"; one unreviewed fix added a wall-clock assertion that fails by chance.
Bug C: `review_launch.repo_paths` refused `--file <scratchpad brief>` as outside the repo, so the caller's checks
never reached the reviewers.

1. `review_loop_scoped_tests.py`: when the run has no scoped test commands and no `--test`, after the last fix pass
   derive commands for the changed files with `gate_commands.derive_gate_commands` (call it; do not edit it), run
   them, and report their pass and fail counts in `scoped_tests`. When none derive, the line says why.
2. When the loop's round budget is spent and the last pass was a coder pass, dispatch one `code-reviewer` read of the
   last fix diff (report only, no coder after it). Its findings go to `findings_remaining`; with none, the packet's
   `unreviewed_fix` is False. Put this in a sibling module.
3. `review_launch.repo_paths`: a `--file` outside the repo that is an existing file under the session temp root
   (`/tmp/claude-<uid>/` or `$TMPDIR/claude-<uid>/`) is read as a reviewer brief: its text reaches every reviewer
   prompt through the existing `brief` text. Any other path outside the repo still stops, and the message names
   both forms.

#### Automated Verification

- [ ] **Derived tests and final read**: a run with no test commands that changes a test file runs the derived command and reports its counts; a run whose budget ends on a coder pass dispatches one final reviewer and records its findings as remaining - `python3 tests/parallel_tests.py test_review_loop_script.py`
- [ ] **Scratchpad brief**: a file flag naming a brief under the session temp root reaches the reviewer prompt; one naming /etc/hosts still stops - `python3 tests/parallel_tests.py test_review_launch.py`

## Phase 8: a /code resume keeps the phase base; code_review_start takes an ancestor base; code_wait never returns an earlier phase's packet

Bug A: when /code stops on a gate, the user commits the phase and resumes. `phase_start.py` then records HEAD, after
that commit and any merge, as the phase base. The review checks an empty diff and reports converged.
Bug B: on a resume the orchestrator passed the integration-branch merge-base as `--base`; `unchanged_dirty_files`
refused it because it differs from the recorded head, so the review never ran.
Bug C: in the same run `code_wait.py review` returned a packet from an earlier phase.

1. `phase_start.py --resume`: when the kept start record's head is an ancestor of HEAD, keep the record and print the
   record's head as the phase base (not HEAD). With no record, or a head that is not an ancestor, print HEAD as now
   and say so on stderr. `skills/code/SKILL.md`: the resume line runs `phase_start.py --resume`.
2. `phase_start.unchanged_dirty_files`: accept a `base_commit` that is an ancestor of the recorded head, or that the
   recorded head is an ancestor of (a resume base). Refuse any other, and the message names `--base <recorded head>`
   and the ancestor rule.
3. Merge commits from the integration branch are left out of the review diff: when `base..HEAD` holds a merge commit,
   `code_review_start.py` reviews against a synthetic base: the tree of `git merge-tree --write-tree <base>
   <merged parent>` for each merged-in parent, made a commit object with `git commit-tree` (no ref), and passes that
   commit as the loop's base. A merge-tree conflict stops with the merge named.
4. `code_wait.py review`: return a packet only when its loop folder is the one this phase's `code_review_start.py`
   recorded in `run.json` (add the folder to the record). Any other folder exits 1 naming both folders and the
   restart step.

#### Automated Verification

- [ ] **Resume base**: after a phase commit, the resume flag prints the pre-commit head - `python3 tests/parallel_tests.py test_phase_start.py`
- [ ] **Ancestor base and merges**: a merge-base base that is an ancestor is accepted; an unrelated commit is refused with the flag named; with a merge commit after the phase, the review diff holds only the phase's change - `python3 tests/parallel_tests.py test_code_review_start.py`
- [ ] **No stale packet**: a loop-dir pointing at an earlier phase's folder is not returned - `python3 tests/parallel_tests.py test_code_wait.py`

## Phase 9: an adopted plan impact reaches the resume round's fix coder

Bug: on `/review resume` with a user ruling that adopts a plan-impact change, the round recorded the ruling under Plan
Deviations and ran the named tests, but no fix coder applied the change. All three reviewers reported the ruling
missing from code, tests and docs, and the round stopped again. `review_user_ruled.leave_out_ruled_impacts` drops
every plan-change finding a recorded ruling settled from the fix list, adopted ones included.

1. `review_user_ruled.py`: a finding settled by a ruling that adopts the change (read the ruling's decision from the
   `PLAN_IMPACT_RULED` row through `handback_store.rulings`; add the decision to `Rulings` there if it is not carried)
   stays in the fix coder's list, marked as user-ruled (adopted, with the ruling's who and when), before any test or
   reviewer runs. Only a ruling that keeps the plan (rejects the change) drops the finding. When the resume holds an
   adopted ruling whose finding text is not among the findings, add the ruling's text as a finding.
2. After that fix pass: an adopted ruling whose finding the coder skipped, or that left no fix diff, fails the round
   with a blocker naming the ruling; no reviewer runs on that round. Put the check in `review_loop_ruled.py`, as new
   functions only: leave the user-only ask filing path (`approval_only_paths`, `approval_ask_text`, the
   `user_only_asks` / `user_only_paths` / `user_only_bases` code and its methods) untouched, since another lane edits it.
3. Touch nothing in `review_fix.py` (`command_decide`, `decide_from_hand_back` and `hand_back_plan_impacts` belong to
   another lane).

#### Automated Verification

- [ ] **Adopted ruling kept**: an adopted ruling keeps its finding in the fix list; a keep ruling drops it; an adopted ruling with no matching finding adds one - `python3 tests/parallel_tests.py test_review_user_ruled.py`
- [ ] **No-diff blocker**: a fake coder that changes nothing for an adopted ruling ends the round with the blocker naming the ruling and no reviewer call - `python3 tests/parallel_tests.py test_review_loop_ruled.py`

## Phase 10: a recorded standing ruling settles the criterion rewords it covers

Bug: the user gave a standing order that every criterion reword follows one rule. The review fork still stopped three
times to ask for sign-off on rewords that order settled. The script half only: the global CLAUDE.md is not edited
(session agent-evals-5e ruling, 2026-11-19).

1. `lib/plan_format.py`: one form and one reader for a standing ruling, a line in the plan's `## Plan Deviations`
   section or in `03-decisions.md` beside the plan:
   `Standing ruling by <who> at <YYYY-MM-DD>: "<the user's quoted words>" covers: rewords`. Add
   `standing_rulings(plan_path) -> list[{who, at, quote, covers}]`; a line that starts `Standing ruling` and does not
   parse raises `PlanFormatError` with the file, the line and the expected form. `covers` is `rewords` only; a cut or
   a narrowing is never covered.
2. `ac_drift_failures`: a ticket criterion with no verbatim AC passes when a standing ruling covers rewords and an AC
   in the criteria file names it (`Ticket #<n>`), so the change is a reword, not a cut. A ticket criterion that no AC
   names still fails.
3. `review/review_fix_plan_impacts.py` `present_plan_impacts`: a held plan impact whose change rewords a criterion
   (the impact keeps the criterion's id and only changes its words; read the kind from the impact row, adding a
   `reword` kind where the packet builds the impact when no field carries it) is adopted with no question when the
   plan holds a standing ruling covering rewords. It prints a deviation line that names the standing ruling (who,
   at) in place of a new sign-off. Every other held impact still goes to the user in the one closing question.
4. Record the cut of the CLAUDE.md half under the queue item's Rulings.

#### Automated Verification

- [ ] **Standing ruling form**: a well-formed standing ruling line parses; a malformed one raises with the line named; a reword whose AC names the ticket criterion passes drift with the ruling and fails without it; a criterion no AC names still fails - `python3 tests/parallel_tests.py test_plan_format.py`
- [ ] **No reword question**: a held reword impact with a standing ruling prints a deviation line naming the ruling and no ask; a held cut impact still asks - `python3 tests/parallel_tests.py test_review_fix_script.py`
