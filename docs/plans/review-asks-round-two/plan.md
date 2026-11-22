# Review asks round two: finding locations, unlocated asks, approval-file asks, held criterion asks, reviewer reports, notes-only staleness

Fix thirteen queue items from /code, /review and /verify-branch runs. Each phase starts with a test that fails on the
current tree. Scripts live in `claude/.claude/scripts/`; tests in `tests/scripts/`, paths from
`tests/scripts/toolkit_paths.py`.

## Scope

- In: `review/verify-prep`, `review/verify_common.py`, `review/finding_record.py`, `lib/script_utils.py` (location
  helpers only), `review/review_asks.py`, `review/review_fix_asks.py` (call sites only: it is over 1000 lines, so new
  logic goes in a sibling module), `review/review_loop_ruled.py`, `review/approval_asks_store.py`,
  `review/phase_asks.py`, `review/review_loop_closure.py`, `review/review_loop_findings.py`, `review/review_fix.py`,
  `review/reviewer_dispatch.py`, `code/code_wait.py`, `code/code_review_start.py`, the
  `/code` skill's phase-asks paragraph (`skills/code/SKILL.md`), the docstrings of `lib/reviewed_tree.py`,
  `review/review_commit_gate.py` and `review/verify-log`, the `/verify-branch` skill's staleness paragraph and exit
  table, `lib/ruled_change_text.py`, `review/review_launch.py`, `gates/waiting_review_launch.py`,
  `review/review_loop_pass_checks.py` (or a new mixin), `review/review_loop_coder.py`, `review/full_check_gate.py`,
  new `review/accepted_failures.py`, the comment-line helper of `code/stale_prose.py`, and the tests of each.
- Out: the shell gates (`gates/shell_write_gate.py`, `lib/shell_statements.py`, `lib/shell_command.py`,
  `lib/inline_interpreter_hint.py`), owned by another lane; `review/review_loop_script.py` and `review/review_fix.py`
  get no new route or state field; any CLAUDE.md and `settings.json`; agent bodies.

## Phase Status

- [x] Phase 1: notes written after the branch review do not make it stale (risk: low)
- [x] Phase 2: a quoted path:line later in a finding is not its location (risk: medium)
- [x] Phase 3: an accepted ask with no location must name what to change (risk: low)
- [x] Phase 4: an accepted approval-file ask restores the pre-pass text, not HEAD (risk: medium)
- [x] Phase 5: a fix pass's approval-file edit becomes a user-only ask carrying the wanted change (risk: medium)
- [x] Phase 6: reviewer dispatch lines give the exact prompt and say who writes the report (risk: low)
- [x] Phase 7: a phase ask that names a user-owned criterion is held for the user (risk: medium)
- [x] Phase 8: a ruling that asks for a test edit is not a no-code ruling (risk: low)
- [x] Phase 9: a review launch refuses to stop a loop another skill started (risk: low)
- [x] Phase 10: the session-start notice skips a loop from another branch or an older session (risk: low)
- [x] Phase 11: a fix pass that deletes a comment files an ask (risk: medium)
- [x] Phase 12: a fix coder that dies mid-edit leaves a record and its findings stay open (risk: medium)
- [x] Phase 13: a recorded acceptance clears a known pre-existing scoped failure (risk: medium)

## Plan Deviations

- Phase 12 step 1: the dead-coder record lives in `<git dir>/review-fix/`, not the run folder: a relaunch gets a new
  run folder and could not find it there. Findings on a reverted approval-only path stay out of the record: they are
  asks, not unverified fixes. Ruled by the lane session, 2026-11-22 (criteria owner: plan).
- AC12 and Phase 12 step 1: "a fix coder" means a pass sent findings; a gate, lint, prose or restore pass that dies
  saves no record, since it holds no findings to re-dispatch. An abnormal end is a non-zero exit, a timeout, an
  `is_error` reply or no final report; a limit line arrives as one of these. Ruled by the lane session, 2026-11-22
  (criteria owner: plan).
- Phase 7 narrows the queue item's "a reviewer question that changes a criterion" to a question that names a
  criterion id held in the plan's `acceptance-criteria.md`: the script has no model call, and a criterion change a
  reviewer writes as a PLAN-IMPACT is already routed by the criteria owner. Ruled by the lane session, 2026-11-20
  (criteria owner of the queue item: session).
- Phase 2 keeps the finding quoted-span pattern in `lib/script_utils.py`. A move to `lib/message_text.py` was tried
  and withdrawn: tests copy `script_utils.py` alone, so a new import breaks them. Ruled by the lane session,
  2026-11-20.
- AC2 reworded to "first named path has a directory part": a dirless name or a `~/` path is not a bare-path
  location. The queue item's incident path had a directory, so its words stay met. Ruled by the lane session,
  2026-11-20 (criteria owner: plan).
- Phase 3 items 1-3 ruled (session, 2026-11-20): the rerun-command ask is closed as fixed by the per-call-site
  command; AC3's second clause is met when the coder findings text of a taken unlocated ask carries the change that
  names the file; a folder-less name stays as `names_a_file` reads it, and the refusal says a root file is written
  `./name.ext`.
- AC4's restore covers the first ruling; an `asks-done --correct` that turns an approval-file ask to accepted after its pre-pass base was released is refused, naming the file, so the user restores their lines by hand (ruling, lane session, 2026-11-20).
- Phase 4: new review-fix state key restored_approval_indexes (lib/review_fix_names.py, listed in SAME_RUN_STATE_KEYS) records which asks were restored; the Scope line "no new state field" is adopted as meaning no new route, ruled by the session, 2026-11-20. Criteria unchanged.
- Phase 5: record_skips in review/review_loop_script.py stops seeding open fixes with reverted approval-file findings (they are user-only asks now); no new route or state field. Eight tests of the old open-fix behavior rewritten. Adopted, no criterion changed (session, 2026-11-20).
- AC5 covers a reverted approval-file edit that a finding names; an edit no finding names stays report-only per hooks-and-handoff AC6. Ruled by the lane session, 2026-11-21.
- AC6 and Phase 6 step 1 scoped: the code-fork route says `code_wait.py review` writes each report; the
  `reviewer_dispatch.py wait` route says the main session writes it. The queue item's words stay met. Ruled by the
  lane session, 2026-11-21 (criteria owner: plan).
- Phase 7: SKILL.md plan impact rejected (no skill edit); phase_asks text for a held criterion ask says to put it on the phase-end list and rule with --by user. Ruled by the lane session, 2026-11-21.
- Phase 8 reads a clause after "no code change" as a test edit when it starts with an edit verb AND names a test word. Verbs: add, pin, change, extend, cover, update, write, create, include, adjust, fix. The verb may follow lead-ins: but, and, also, then, plus, please, just, instead, so, now, still. Test words: test, case, fixture, and their plurals; an underscore counts as a word break, so `test_x.py` names a test. Clauses break at ; and , at a period or colon followed by a space or the end, at a parenthesis that holds text (an empty `()` does not break), at en and em dashes, at double hyphens and at a spaced hyphen. A verb followed by no, nothing, none or not ("add no new test") is not an edit. The plain OR rule (a verb or a test word alone) was narrowed because the two fixtures in tests/scripts/no_code_notes.py ("add one Watch line", "a reviewer-only case") must stay no-code. These lists are closed (lists closed by the lane session, 2026-11-21): another unlisted verb or lead-in raised by a re-review is recorded as rejected with no code change. No criterion changed (AC8 holds). Adopted by the session, 2026-11-21.
- Phase 9 step 1: the refusal names a stop-and-relaunch step, not `reviewer_dispatch.py wait`, which would hand the
  refused run the other loop's reviewer dispatches. The skill comes from `--skill` in `packet_args`, so no new
  `launch.json` key. No criterion changed (AC9 holds). Ruled by the lane session, 2026-11-21.
- Phase 9: `--skill` holds the run mode (fix or review), so the refusal compares run modes. The incident (a /fix
  launch beside a /review loop, then the /review relaunch beside the /fix loop) is refused both ways. A /fix launch
  beside /review's own accepted-asks fix loop still replaces it: no session hit that, and a launching-skill key is
  left out (toolkit-script-rules Size). Ruled by the lane session, 2026-11-21.
- AC10 and Phase 10 step 1: the before-session-start age test is dropped: the registry start is the process start,
  so a resumed or compacted conversation's own loops would be hidden. The notice filters by branch and detach and
  prints each loop's age and branch. The incident (another branch, 7 days old) is still left out. Ruled by the lane
  session, 2026-11-21 (criteria owner: plan).
- AC10: the detached-HEAD ask is rejected, no criterion change. A launch from a detached HEAD stays kept and
  dispatched, and the pinned test stays; no session hit that case (toolkit-script-rules Size). Ruled by the lane
  session, 2026-11-21.
- Branch review ask (scripts CLAUDE.md Owners list lacks the six new owners): rejected, no CLAUDE.md edit. The owner
  facts go in the module docstrings of accepted_failures, review_loop_partial_fix, review_loop_pass_names,
  approval_restore, number_masking and age_text; the rerun review's ask (is a docstring owner enough for age_text and
  number_masking) is answered by the same ruling. Ruled by agent-evals-c3, 2026-11-22.

## Phase 1: notes written after the branch review do not make it stale

Bug: a lane wrote `docs/changes` notes after its logged branch review; verify-prep counted them as a tree change and
asked for a second branch-wide review over doc-only additions.

1. `verify-prep` main: read `notes_paths.committed_notes_list(top)`; on errors, exit 2 naming them. Save the entries
   in the verify context (key `notesEntries`) and pass them as `notes_entries=` to `vc.tree_fingerprint`.
2. `verify_common.context_fingerprint`: pass `context.get("notesEntries")` as `notes_entries=`, so `verify-log`
   fingerprints the tree the same way prep did. A context saved before this change (no key) fingerprints as today.
3. A change outside the notes paths still makes the review stale.
4. Tests (in `test_verify_branch_script.py`, PrepTest): log a branch review, then add `docs/changes/notes/x.md`; prep
   reports the review as ran. Then edit a code file; prep reports it stale.

#### Automated Verification

- [ ] **Verify branch script**: `python3 tests/parallel_tests.py test_verify_branch_script.py`

## Phase 2: a quoted path:line later in a finding is not its location

Bug: a reviewer finding named `tests/scripts/test_x.py` with no line, then quoted a fixture string holding `a.py:1`.
`finding_record.parse_finding` took `a.py:1` as the location, and the loop skipped the finding as "the file is not
in the tree".

1. `finding_record.parse_finding`: the location is the first path the text names. A `path:line` inside a quoted span
   (double quotes, single quotes bounded by non-word characters, or backticks that hold more than the location
   itself) is not a location. A bare path with a `/` and an extension that comes before any usable `path:line` is
   the location, with line 0.
2. Keep one owner: the finding quoted-span pattern is `FINDING_QUOTED_SPAN` in `lib/script_utils.py`, next to
   `PATH_LINE`, with a comment on how it differs from `message_text.QUOTED_SPAN`; `script_utils.py` imports no new
   module. `parse_finding` uses the location helpers there; add no second path regex.
3. Collect the real finding shapes from `~/.claude/projects/**/subagents/*.jsonl` reviewer reports (`- fix:`,
   `- ask:`, `- nit:`, `- blocker:` bullets), run the new parse over them, and report "parsed N of M" with each
   location that changed.
4. Tests (in `test_review_loop_findings.py`): the real shape `[test-gap] /home/u/repo/tests/scripts/test_x.py
   (test_name) — the test passes ... FINDING ("a.py:1 [plan-drift] PLAN-IMPACT: ...")` gets the test file as its
   file_line, and the loop's skip reason is not `the file is not in the tree`. A leading backticked `path:line` is
   still the location.

#### Automated Verification

- [ ] **Finding location**: `python3 tests/parallel_tests.py test_review_loop_findings.py`
- [ ] **Loop script**: `python3 tests/parallel_tests.py test_review_loop_script.py`

## Phase 3: an accepted ask with no location must name what to change

Bug: `review_fix_asks.ask_finding_text` drops the question on purpose (it can hold a declined branch). An accepted
`[design-decision]` ask with no file_line reached the fix coder as a bare `Proposed change: ...` with no location and
no subject.

1. Add `refuse_unlocated_changes(asks, outcomes, notes, rerun_command)` in `review_asks.py`, beside
   `is_conditional_change`: an `accepted` outcome on a finding ask (not plan-impact) whose file_line is empty or
   `handback.UNLOCATED`, and whose change names no file (`script_utils.names_a_file`), and a `modified:` outcome on
   such an ask whose note names no file, raises the same UsageError type `refuse_conditional_changes` raises.
   The message names the ask and asks for `'modified:<the change, naming the file and the edit>'`, and says nothing
   was logged.
2. Call it in `review_fix_asks.py` at both `refuse_conditional_changes` call sites (asks-done and `--correct`).
3. A `modified:` outcome whose text names a path is taken. A `modified:` note that names no file is refused on an
   unlocated ask.
4. Tests (in `test_review_asks.py` or `test_review_fix_ask_ruler.py`): asks-done with `accepted` on an unlocated
   design-decision ask whose change names no file exits 2, logs nothing, and the message asks for `modified:`; the
   same call with `modified:<change naming a file>` logs, and the findings file sent to the coder names that file.

#### Automated Verification

- [ ] **Unlocated ask refusal**: `python3 tests/parallel_tests.py test_review_asks.py`
- [ ] **Ask ruler**: `python3 tests/parallel_tests.py test_review_fix_ask_ruler.py`

## Phase 4: an accepted approval-file ask restores the pre-pass text, not HEAD

Bug: accepting "revert the fix coder's edit to CLAUDE.md" let the next fix coder reset the file to HEAD, which also
removed uncommitted lines the user had applied and kept.

1. When a user-only approval ask (`approval_asks_store.approval_change`) is ruled `accepted`, in asks-done and in
   `phase_asks rule --by user`, restore the file to its saved pre-pass blob (`approval_asks_store` paths map,
   `script_utils.restore_blob`) before `forget_ruled_approval_paths`, and leave that ask out of the findings file the
   fix coder gets.
2. A base that is unknown (unhashable, or no snapshot) is told apart from an absent file (blob None): an unknown base
   keeps today's path (the coder reverts). Store the unknown case as its own value, not None.
3. A restore that fails exits non-zero naming the file and the blob, and logs nothing.
4. Tests (in `test_review_loop_ruled.py` and `test_phase_asks.py`): a CLAUDE.md with uncommitted user lines, then a
   fix-pass coder edit filed as an approval ask; after `accepted --by user`, the user lines remain, the coder edit is
   gone, and the findings file holds no item for it. An approval ask with an unknown base still reaches the coder.

#### Automated Verification

- [ ] **Approval restore in the loop**: `python3 tests/parallel_tests.py test_review_loop_ruled.py`
- [ ] **Approval restore in phase asks**: `python3 tests/parallel_tests.py test_phase_asks.py`
- [ ] **Approval chain**: `python3 tests/parallel_tests.py test_phase_asks_chain.py`

## Phase 5: a fix pass's approval-file edit becomes a user-only ask carrying the wanted change

Bug: a fix coder edited `scripts/CLAUDE.md` in two /review runs; each ended with "revert the fix coder's edit", a
stop that carries no wanted change, and the finding came back open.

1. `review_loop_ruled.ask_for_approval_only_edits` / `keep_reverted_open`: after the revert, each finding on a
   reverted approval-only path becomes a user-only ask (`add_ask` with `user_only`) whose change is the finding's
   proposed change, in place of an open fix.
2. The file stays at its pre-pass text. The revert-failed and unknown-base paths keep today's revert ask.
3. Tests (in `test_review_loop_ruled.py`): a fix pass whose coder edits CLAUDE.md for a finding ends with a
   user-only ask carrying that finding's change, the file byte-equal to its pre-pass text, and no open fix for it.

#### Automated Verification

- [ ] **Approval edit becomes an ask**: `python3 tests/parallel_tests.py test_review_loop_ruled.py`
- [ ] **User-ruled asks**: `python3 tests/parallel_tests.py test_review_user_ruled.py`

## Phase 6: reviewer dispatch lines give the exact prompt and say who writes the report

Bug: a code-fork told reviewers "Write your report to <report file>"; the code-reviewer, test-reviewer and
smell-reviewer have no Write tool, so it dispatched coders to save their reports and later ran reviewers as
general-purpose.

1. `reviewer_dispatch.request_lines`: each line gives the Agent prompt word for word, `prompt "Read <prompt file>
   whole and do that task."`, and takes the writer note from its caller: the code-fork route (`code_wait.py review`
   writes each report) and the `reviewer_dispatch.py wait` route (the main session writes it).
2. `code_wait.reviewer_dispatch_lines`: its request lines carry the `code_wait.py review` writer note; its
   next-command line adds no second sentence about who writes the reports.
3. Update every reader of the line: the tests that split it, and the skill paragraphs in `skills/code/SKILL.md` and
   `skills/_shared/review-fork-run.md` when their wording no longer matches.
4. Tests (in `test_reviewer_dispatch.py`): the line holds the exact prompt sentence and no instruction to the
   reviewer to write a file.

#### Automated Verification

- [ ] **Dispatch lines**: `python3 tests/parallel_tests.py test_reviewer_dispatch.py`
- [ ] **Fix script reads the line**: `python3 tests/parallel_tests.py test_review_fix_script.py`
- [ ] **Wait command**: `python3 tests/parallel_tests.py test_code_wait.py`

## Phase 7: a phase ask that names a user-owned criterion is held for the user

Bug: `/code` makes the session rule each reviewer question `accepted` or `rejected`; a question whose answer changes
an acceptance criterion is the user's, and the session had no way to hold it.

1. `code_review_start.py` records the plan path in `<git dir>/code-phase/run.json` (key `plan`); `read_phase_run`
   returns it.
2. `phase_asks.record_open`: an ask whose question or change names a criterion id (`plan_format.criterion_ids_in`)
   that the plan's `acceptance-criteria.md` holds, when `plan_format.plan_criteria_owner(plan)` is `user`, is opened
   with `user_only` set and the ids saved on the ask (`criteria`). Owner `session` or `plan`, or no plan: unchanged.
3. `phase_asks list` and the open notice name the criterion ids beside the held ask. The existing refusal of a
   session ruling on a user_only ask, and the `--by user` row with who and when, carry it from there.
4. `phase_asks list` prints, after the list, one line naming each held ask's criteria and the next step (do not
   rule it; put it on the phase-end list with its question and criteria; the user rules it with
   `phase_asks.py rule --by user`). No code change. An ask already `user_only` passes through unchanged.
5. Tests (in `test_phase_asks.py`): a phase packet ask naming AC2, plan criteria owned by the user: list marks it
   user only and names AC2; a session rule exits 2 and logs nothing; a `--by user` rule logs the row decided by the
   user with its time, and the phase asks read as ruled. The same ask with criteria owned by `plan` opens as a plain
   ask.

#### Automated Verification

- [ ] **Held criterion ask**: `python3 tests/parallel_tests.py test_phase_asks.py`
- [ ] **Run record**: `python3 tests/parallel_tests.py test_code_review_start.py`
- [ ] **Phase asks chain**: `python3 tests/parallel_tests.py test_phase_asks_chain.py`

## Phase 8: a ruling that asks for a test edit is not a no-code ruling

Bug: a resume ruling "no code change; add a case to the test loop and pin the output" was read as no code change, so
the fixer skipped the test edit.

1. `lib/ruled_change_text.py` `is_no_code_ruling`: false when the note, after the "no code change" words, asks for an
   edit: a clause that starts with add, pin, change, extend, cover, update, write, create, include, adjust or fix
   (after optional lead-ins but, and, also, then, plus, please, just, instead, so, now, still) AND names a test word
   (`test`, `case`, `fixture`, plurals included; an underscore is a word break, so `test_x.py` counts). Clauses break
   at `;` and `,`, at a period or colon followed by a space or the end, at a parenthesis that holds text (an empty
   `()` does not break), at en and em dashes, at double hyphens and at a spaced
   hyphen. A verb followed by no, nothing, none or not (`add no new test`) is not an edit. The lists are closed
   (lists closed by the lane session, 2026-11-21): another unlisted verb or lead-in raised by a re-review is recorded as rejected with no code change.
   Every caller goes through it; no second regex.
2. Tests (new `test_ruled_change_text.py`, or the existing test of its callers): the incident note reads as a change;
   "no code change" and "no code change; the current text is right" still read as no code.

#### Automated Verification

- [ ] **Test-only ruling**: `python3 tests/parallel_tests.py test_ruled_change_text.py`

## Phase 9: a review launch refuses to stop a loop another skill started

Bug: `/fix` launched in a worktree where a `/review` loop ran, and `review_launch` SIGTERMed it; the relaunch killed
the `/fix` loop in turn. Neither said so first.

1. `review_launch.stop_earlier_loops`: read each live loop's `launch.json`. A live loop of the same repo whose skill
   differs from this launch's makes the launch exit with a LaunchError that names the loop id, its skill, its pid and
   the next step "End the run with a stop that names this loop; launch again after pid <pid> exits.", before any
   folder is made. A same-skill live loop (the
   resume and retry path) is still stopped, with the existing line. A `launch.json` with no skill reads as a
   different skill.
2. Read the launching skill from `--skill` in the saved `packet_args` of `launch.json`; add no new key.
3. Tests (in the launch test file): a live `/review` loop and a `/fix` launch: exit 2, the loop's pid still alive,
   the message names the loop; a live `/fix` loop and a `/fix` relaunch: the old loop is stopped.

#### Automated Verification

- [ ] **Launch refusal**: `python3 tests/parallel_tests.py test_review_launch.py`

## Phase 10: the session-start notice skips a loop from another branch or an older session

Bug: on a compacted resume, the SessionStart hook printed `ACTION: dispatch-reviewer` for a 7-day-old loop scoped to
another branch, and said it was launched in this session.

1. `reviewer_dispatch.waiting_launch_lines`: leave out a loop whose `launch.json` branch differs from the repo's
   current branch. Add no test against the session's start time. Save the branch and launch time in `launch.json`
   when they are not there yet. A loop left out is named on one line with its age and branch, with no ACTION; a loop
   kept also shows its age and branch.
2. A loop launched detached for a code fork (`code_wait.py review` writes its reports) is left out the same way: save
   `"detach": true` in `launch.json` and skip it. This takes the Phase 6 held ask.
3. HEADER no longer says "launched earlier in this session"; it says the loop's age and branch.
4. Tests (in `test_reviewer_dispatch.py` and the hook's test): a live loop on another branch prints no ACTION; a
   live loop on this branch launched after the session start prints its ACTION with age and branch; a detached loop
   prints no ACTION.

#### Automated Verification

- [ ] **Stale loop notice**: `python3 tests/parallel_tests.py test_reviewer_dispatch.py`
- [ ] **Hook**: `python3 tests/parallel_tests.py test_waiting_review_launch.py`

## Phase 11: a fix pass that deletes a comment files an ask

Bug: a `/review` fix pass deleted an existing code comment and listed it as a fix; the repo rule says comments go
only with the user's permission.

1. After each fix pass, the loop reads the removed comment lines of the pass diff with
   `code/stale_prose.comment_lines_of_side(..., "removed")` (move it to a lib module if review code cannot import
   it). A removed comment line that no finding names is put back through `lib/protected_lines.py` and filed as an
   ask carrying the removal, the way approval-only edits are. Code in a new mixin or `review_loop_pass_checks.py`;
   `review_loop_script.py` gets one call.
2. A comment line the pass rewrote (removed and re-added with changed words on the same line) counts as removed only
   when no finding names its file and line.
3. Tests (in `test_review_loop_script.py` or a new test file for the mixin): a fix pass that deletes an unnamed
   comment: the line is back and an ask names it; a pass that deletes a comment a finding names: kept deleted, no
   ask.

#### Automated Verification

- [ ] **Comment removal ask**: `python3 tests/parallel_tests.py test_review_loop_script.py`

## Phase 12: a fix coder that dies mid-edit leaves a record and its findings stay open

Bug: a fix coder stopped on a spend limit partway through; the tree held a partial edit and nothing said which
findings landed.

1. On a coder call that ends abnormally (non-zero exit, a timeout, an `is_error` reply, no final report), the loop writes
   `partial-fix.json` in `<git dir>/review-fix/`: the findings it gave the coder, the pass diff, and the time. The stop note
   names each of those findings as unverified and the record's path.
2. The next launch on the same repo with that record re-queues its findings as open fixes against the current tree
   and removes the record after the pass. Code in `review_loop_coder.py` or a new sibling; `review_loop_script.py`
   and `review_fix.py` get call sites only.
3. Tests: a fake coder that edits one file and exits non-zero: the record holds the findings and the diff, the stop
   note names them; a relaunch dispatches those findings and the record is gone after the pass.

#### Automated Verification

- [ ] **Dead coder record**: `python3 tests/parallel_tests.py test_review_loop_coder.py`

## Phase 13: a recorded acceptance clears a known pre-existing scoped failure

Bug: scoped tests failed at HEAD and on the branch with differing throttling lines (429), so `is_pre_existing` read
them as new; the loop ended critical-blocker and no verb cleared it.

1. New `review/accepted_failures.py` with `accept --repo <r> --line <failing line> --by <who> --reason <text>` and
   `list`. Rows live in the git dir, written through `write_text_atomically`. Never a verb in `review_fix.py`.
2. `full_check_gate.scoped_failures_pre_existing`: a head failing line that an accepted row names, and that also
   fails in the base run, counts as pre-existing; new log lines that only differ in a number or a timestamp from a
   base line do not count as new error lines for an accepted test.
3. A critical-blocker stop for scoped failures prints the `accept` command with the failing lines filled in.
4. Tests (in the full-check gate test file): a scoped failure present at base with a changed 429 line: blocker
   without a row, pre-existing with a row; a new failing test with a row for another line: still a blocker.

#### Automated Verification

- [ ] **Accepted failure**: `python3 tests/parallel_tests.py test_full_check_gate.py`

## Final check

- `bash tests/lint.sh <changed .py files>` and `bash tests/run.sh` pass.
