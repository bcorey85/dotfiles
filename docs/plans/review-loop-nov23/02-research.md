---
date: 2026-11-23
git_commit: 0236c779f360bdeae727873427c109718ae3b64c
branch: fix/review-loop-nov23
topic: Review loop state, ask rulings, relay, rounds and cap, reviewer reports, stop text, and the /code review step
tags: [review-loop, phase-asks, relay, session-registry, code-step, tests]
status: complete
---

# Research: Review loop state, ask rulings, relay, rounds and cap, reviewer reports, stop text, /code review step

Paths are under `claude/.claude/scripts/` unless they start with `tests/` or `claude/.claude/skills/`.

## Findings

### 1. Session records, `session_registry.py`, `session_id_of_name`, and `--relayed-by`

- Session records are `<pid>.json` files in `sessions_dir()` (`$CLAUDE_CONFIG_DIR/sessions`, else `~/.claude/sessions`): `lib/session_registry.py:21`. `projects_dir()` is at `:29`.
- `live_session_rows()` (`lib/session_registry.py:44`) reads those files and keeps dict rows whose `pid` is an int, not a bool, and alive.
- `row_for_name(name)` (`:61`) returns the first live row with that name. Its only caller outside the module is `tools/session_pane.py`.
- `session_display_name(session_id)` is at `lib/session_registry.py:91`.
- `session_id_of_name` is not in `session_registry.py`. It is at `lib/human_turn_lookup.py:31`. It matches `live_session_rows()` on `name` and raises `HumanTurnRefusedError` when no live row has the name, when several do, or when the row has no `sessionId`.
- `transcript_of_session(session_id)` (`lib/human_turn_lookup.py:45`) globs `projects_dir()/*/<id>.jsonl` and needs exactly one match.
- `verified_human_turn(session_name, after_epoch)` (`lib/human_turn_lookup.py:113`) returns the latest human turn after `after_epoch`. It carries `HumanTurn(timestamp, epoch)`, the time only, never the words.
- `--relayed-by` parsing:
  - `pop_relay_options(words)` at `review/ruling_relay.py:41` refuses the retired `--quote` and an empty `--relayed-by`. It returns `(rest, RelayRequest | None)`. `RelayRequest` holds `relayed_by`.
  - `verify_relay(request, filed_at)` is at `review/ruling_relay.py:86`. `record_relay(session_id, repo, relayed, asks)` is at `:93`.
  - Flag text constants: `RELAYED_BY_FLAG`, `RETIRED_QUOTE_FLAG`, `RELAY_USAGE` in `lib/ask_outcome_words.py`.
- `asks-done`:
  - `asks_done_options` (`review/review_fix_asks.py:184`) pops `--by` (user or session), then the relay options, then `--packet` and `--correct`.
  - `verified_fix_relay` is at `:206`. `record_unrecorded_relay` is at `:220`; it uses the state key `asks_relay_recorded` so each finding is relayed once.
  - The `ask-ruling-relayed` row is written by `record_relayed_ruling` (`review/handback_store.py:223`). Its fields are `repo`, `ruler`, `relayed_by`, `turn_ts` and `finding_ids`. Nothing is written without a session id or without user_only asks.
- `decide`:
  - `pop_decide_relay` is at `review/review_fix_plan_impacts.py:56`.
  - `verified_decide_relay` (`:65`) refuses a relay under `--by session`, an impact with no filed time, or no human turn after `filed_at`.
  - `relayed_owner` (`:99`) appends `, relayed by session <name> (user turn at <ts>)` to the owner string.
  - `write_ruling_entry` (`:107`) writes the plan-deviation entry and the ruled-impact rows. For a relay it also writes a `plan-ruling-relayed` row through `record_relayed_plan_ruling` (`review/handback_store.py:123`).
  - Caller: `command_decide` in `review/review_fix.py` (uses `verified_decide_relay` at `:801`, `decide_from_hand_back` `:804`, `record_plan_ruling` `:805`).
- `phase_asks.py rule` pops relay options in `split_ruler` (`review/phase_asks.py:253`).

### 2. State between runs and the stored outcome of an ask

- Hand-back store: JSONL per session id under `~/.claude/state/handback/<session>.jsonl` (or `$HANDBACK_STORE_DIR`), appended by `handback_store.record`. Stale-file age is `STALE_STORE_SECONDS = 7*86400` (`review/handback_store.py:23`).
- Row kinds in `review/handback_store.py`: `ASK_REJECTED`, `ASK_REJECTION_WITHDRAWN`, `ASKS_LOGGED_ROW`, `ASK_RULING_RELAYED` (`:47`), `PLAN_RULING_RELAYED` (`:50`), `PLAN_IMPACT_RULED`, `PLAN_IMPACT_APPLIED`, `PHASE_ASKS_OPEN`, `PHASE_ASKS_RULED`.
- Readers and writers: `record_ruled_impact` (`:96`), `rulings(session_id, repo)` (`:188`) returning `Rulings(impacts, finding_texts, adopted)`, `record_rejected_ask` (`:210`), `rejected_ask_rows` (`:238`), `record_phase_asks_open` (`:645`), `unruled_phase_asks` (`:690`), `ruled_rows_repo`.
- Ruling rows are keyed by `repo` (the work-tree top, `ruled_rows_repo`), not by branch.
- Review-fix files in `<git dir>/review-fix/`, with names in `lib/review_fix_names.py`: `state.json` (`STATE_FILE_NAME`), `approval-asks.json` (`APPROVAL_ASKS_NAME`), `held-approval-changes.json` (`HELD_APPROVAL_NAME`), `partial-fix.json` (`PARTIAL_FIX_NAME`), `ask-findings.md` (`ASK_FINDINGS_NAME`).
- `approval-asks.json` shape: `{"paths": {path: blob | null | "unknown"}, "wanted": [{text, change, path, line, title}]}`. Functions are in `review/approval_asks_store.py`: `read_saved_asks` (`:81`), `write_saved_asks` (`:118`), `check_approval_paths_readable` (`:179`), `forget_ruled_approval_paths` (`:189`; drops a ruled path or wanted entry, accepted or rejected).
- `partial-fix.json` (`review/review_loop_partial_fix.py`) holds `findings`, `diff`, `time` and `branch`. `saved_findings(repo)` raises `SavedRecordError` for a branch mismatch (a null branch skips the check).
- `SAME_RUN_STATE_KEYS` in `review/review_fix_state.py` includes `asks_relay_recorded`, `ask_outcomes`, `ask_notes`, `asks_decided_by`, `waiting_packets`, `relaunch_args`.
- An outcome is logged by `log_ask_outcome` (`review/review_asks.py:309`), which runs `skills/review/log-review-finding` with `ask_outcome=<accepted|rejected>` and `ask_decided_by=<ruler>`. `applied` logs as accepted. A rejection is also stored as an `ask-rejected` row (`record_rejected_asks`, `review/review_asks.py:353`).
- Read back: `build_loop` (`review/review_loop_main.py:115`) sets `loop.rejected_asks` and `loop.rejected_questions` from those rows for the session and repo (`:126-127`). `rejected_ask_records` and `rejected_ask_questions` are in `review/review_loop_ruled.py:89,97`.
- Header lines carry rulings into a run: `user-ruled`, `user-ruled-at`, `session-ruled`, and `adopted` (JSON), keys in `review/review_loop_prompt_file.py`. `review/review_launch.py:234` (`header_pairs`) writes them from `--user-ruled N` and `--session-ruled N`.

### 3. `phase_asks.py`

- `user_only` classification:
  - `user_owned_criteria` (`review/phase_asks.py:99`) and `hold_criterion_asks` (`:124`) mark an ask `user_only` with `criteria` when its question or change names a criterion id the plan assigns to the user (`plan_format.plan_criteria_owner`).
  - In the loop, asks on approval-only files are put in `user_only_asks`. The packet writer `ask_entry` (`review/review_loop_packet.py:42`) sets the `user_only` key for them.
- `rule`:
  - `RULABLE_OUTCOMES = (ACCEPTED, REJECTED)` (`:67`). `read_rulings` (`:219`) calls `review_asks.parse_outcome_words(words, count, RULABLE_OUTCOMES, RULABLE_OUTCOMES)` (`review/review_asks.py:88`). The word form is `accepted:<reason>` or `rejected:<reason>`; a missing reason is refused.
  - `--by`: `split_ruler` (`:253`) accepts only `user`; no `--by` means session; any other value is refused with "--by takes only `user`". `ruler_of_call` (`:283`) refuses a session ruling on a user_only ask through `review_asks.user_only_refusal` (`review/review_asks.py:226`).
  - All asks in one call: `rule_open_asks` (`:338`) needs the outcome count to equal the open ask count. The refusal reads "N finding ask(s) are open but M outcome(s) were given".
  - Other behavior of `rule_open_asks`: exit 2 without `CLAUDE_CODE_SESSION_ID`; exit 0 "already ruled"; exit 1 for an unwritable store file; then `check_approval_paths_readable`, `restore_accepted_approvals`, `record_rejected_asks`, `forget_ruled_approval_paths`, `log_outcomes` (`:301`), `ruling_relay.record_relay`, and one `PHASE_ASKS_RULED` row per answered open row. `command_rule` (`:327`) holds `phase_asks_lock`.
  - `record_open` (`:153`) opens asks only when `capped_review.effective_status` is in `handback.CLEAN_STATUSES`. `finding_asks` leaves out plan-impact asks.
- Tests: `tests/scripts/test_phase_asks.py` (`UserOnlyAskTest` `:842`, `CriterionAskTest` `:1020`, `OpenPhaseAsksTest` `:597`), `test_phase_asks_rejections.py`, `test_phase_asks_chain.py`, and the relay cases in `test_ruling_relay.py`.

### 4. Intake and comparison with earlier rulings

- `take_review` (`review/review_loop_intake.py:54`): `without_held_findings`, `split_review`, absent files to `skipped_fp` (`ABSENT_FILE_REASON`), `plan_change_items`, `route_plan_items`, `without_impact_repeats`, `record_review`, `add_asks_without_ruling`. It returns `TakenReview(fixes, nits)`.
- Filing helpers: `earlier_filing` (`:80`), `ask_already_filed` (`:87`), `file_finding` (`:114`), `refile` (`:136`), `record_review` (`:145`).
- Comparison with earlier rulings (`review/review_loop_ruled.py`): `without_repeats` (`:283`), `without_rejected` (`:313`, reason `REJECTED_ASK_REASON`), `drops_repeated_ask` (`:323`).
- Matching functions (`review/review_loop_findings.py`): `repeats_a_rejected_ask` (`:424`; same path and `near_title` of the question title), `repeats_an_ask` (`:433`), `refiles_accepted_drift` (`:474`).
- A matching finding is dropped with a reason constant: `REPEATED_ASK_REASON`, `REJECTED_ASK_REASON`, `REVERTED_APPROVAL_EDIT_REASON`, `KEPT_OWNER_LINE_EDIT_REASON`, `POINTER_ASK_REASON`, `NOTE_ASK_REASON`.

### 5. Resume, ruling text into a fix pass, and the pass checks

- `run_loop` (`review/review_loop_main.py:186`): reads the header findings and `partial-fix.json` findings (`saved_findings`, `saved_findings_not_in_header`), sets `user_ruled`, `user_ruled_at`, `adopted`, `session_ruled`, calls `resume_approval_asks` (`review/review_loop_ruled.py:673`), `first_pass` (`review/review_loop_script.py:956`; with findings it runs `fix_first`) and `walk`.
- `resume_approval_asks` files again each saved approval ask whose file still differs from its saved base blob and from HEAD, unless a ruling in the findings, a rejection, or a kept held packet settles it. It also calls `resume_wanted_asks` (`:703`), then `save_approval_paths`.
- Ruling text in a pass: `issue_text` (`:780`) marks a user-accepted finding with `user_ruled_issue`. Ruler clauses and changed-ask text come from `lib/ruled_change_text.py` (`changed_text`, `ruled_note`, `is_no_code_ruling`). `review_fix_asks.py:509-514` adds `--user-ruled N` to the lead launch args.
- Checks on the pass:
  - `check_pass_result` (`review/review_loop_pass_checks.py:18`): a later-phase file edit raises `LaterPhaseEditError`; `change_removal.is_gutted` raises `ChangeRemovedError`; otherwise `note_late_repair`. `run_loop` turns the first into `critical-blocker` and the second into `FIX_REMOVED_CHANGE`.
  - `keep_coder_commit_in_scope` is at `:34`.
  - `review_loop_scope_guard.py`: `ScopeGuard.undo` (`:148`) puts back files outside scope that no finding names; `guard_pass` is at `:221`.
  - `review_loop_ruled_out.py`: `skip_ruled_out` (`:42`), `PassGuard.undo` (`:106`), `begin_pass` (`:131`).
  - `review_loop_final_read.py`: `read_last_fix`, `read_late_repairs`, `read_diffs`, `apply_pending_cap` (see Q6).
- A pass that changes code a ruling named:
  - A no-code ruling: `flag_broken_no_code_rulings` (`review/review_loop_ruled.py:722`) records each changed code file in `no_code_broken` as `{"ruling", "file"}`. The rulings go to the reviewer prompt (`review/review_loop_prompts.py:101,118-120`), and the packet key is `no_code_ruling_broken` (`review/review_loop_script.py:900`).
  - An adopted ruling the pass left unapplied: `stop_on_unapplied` (`review/review_loop_ruled.py:747`) stops as `critical-blocker`, keeps the findings open and sets `adopted_unapplied`.
  - An approval-only file: the pass's change is reverted and the finding becomes a user_only ask (or a dropped repeat of a rejected one).

### 6. Rounds, the cap, and the passes after it

- Constants: `ROUND_BUDGET = 2` and `FIRST_ROUND = 1` (`review/review_loop_script.py:145-146`).
- `next_round` (`:430`) adds 1 to `iter_count`. `review_round()` (`:554`) sets `last_review_round = iter_count` (`:559`). A repair pass raises `iter_count` but not `last_review_round` (comment at `:340`).
- A resumed loop starts at `min(header_iter(header), ROUND_BUDGET - 1)` (`review/review_loop_main.py:157`).
- `walk` (`review/review_loop_script.py:932`): `while iter_count < ROUND_BUDGET and dispatches` runs `next_round`, `review_round`, `fix_round`. Then, while status is `converged`: `read_last_fix(ROUND_BUDGET)` (`:943`), `format_reviewed_files`, `full_check_pass`, `class_closure_pass`, `scoped_tests_pass` (or the gate commands), then `read_late_repairs` and `apply_pending_cap` (`:952-953`). `plan_second_round` (`:720`) is only called when `iter_count < ROUND_BUDGET` (`:675`).
- Cap: `read_last_fix` (`review/review_loop_final_read.py`) runs one `code-reviewer` read when `iter_count >= round_budget` and the last pass was a coder. `read_diffs` sets `cap_pending` when a read files a fix. `apply_pending_cap` (`:89-92`) then calls `stop(CAP_REACHED, [])` if status is still `converged`. `stop` is at `review/review_loop_script.py:434`.
- Class closure: `class_closure_pass` (`:802`); an open class that cannot be fixed lands in `open_classes`.
- Value sources:
  - `CAP_REACHED = "cap-reached"` (`review/capped_review.py:12`). `effective_status` (`:16`) reads a `cap-reached` packet as `deferred` only with no blocker, no open class, no `unrun_reviewer`, a passed full check, and a matching `full_check_tree` fingerprint.
  - `review_round` in the packet: `outcome()` key `review_round` (`review/review_loop_script.py:894`), carried by `packet_message` (`review/review_loop_packet.py:71`) and `EMPTY_OUTCOME` (`:105`). `handback.py` lists it in `INTEGER_KEYS`.
  - Stop text: `STOP_STATUSES[CAP_REACHED]` in `review/review_fix.py:551` ("The review cap was reached. Report these findings; the user decides. Do not re-dispatch. Do not run /fix. ..."). With an open class and touched files, `scoped_rerun_lines` (`:565`) swaps in `SCOPED_RERUN` (scoped re-review launch line with `--iter 0 --file ...`); it is applied at `:608`.
  - Hook: `CAPPED_ON_A_FIX_REASON` (`review/handback_hook.py:62`) denies a cap-reached hand-back that follows a coder no reviewer read. `review/handback.py:510` says "return cap-reached" when `findings_remaining` holds a blocker. `/code` routes `cap-reached` to a STOP (`claude/.claude/skills/code/SKILL.md`, step 5).

### 7. Reviewer reports per round, the dispatch line, and reports that never arrive

- Naming: a request role is `review{iter_count}-{agent}` (`review/review_loop_script.py:447`); the final read uses `review{n}-main` for the untracked-file note. `write_round` (`review/reviewer_dispatch.py:75`) writes `<loop dir>/reviewer-requests/<role>.prompt.md`, `<role>.report.md`, and the manifest `round-<n>.json` (`{"round", "requests": [{role, agent, prompt_file, report_file}]}`) last. A repeated role gets a `-2`, `-3` suffix (`:82-90`).
- Request: `reviews_from_main` (`review/review_loop_script.py:459`) calls `reviewer_dispatch.request_round(...)` with `CALL_TIMEOUT_SECONDS = 1800` (`review/review_loop_calls.py:15`). `request_round` (`:103`) polls every `POLL_SECONDS = 2.0` until every report file holds text.
- Dispatch line:
  - `request_lines` (`:156`) prints `ACTION: dispatch-reviewer` and one line per open request: `- agent <agent>; prompt "Read <prompt_file> whole and do that task."; [model <m>;] report <report_file> <note>`.
  - It lists every request with no report across all rounds (`pending_requests` `:151`, `all_requests` `:140`). There is no per-round filter in the printed line.
  - The wait route is `wait_for_step` (`:180`), with `dispatch_lines` (`:176`). The code-fork route is `code/code_wait.py`: `follow_run` (`:561`), `reviewer_dispatch_lines` (`:546`), `reviewer_pairs` (`:504`; a report file must be one the loop's requests name), `write_finished_reports` (`:520`). The note differs: `SESSION_WRITES_NOTE` vs `CODE_WAIT_WRITES_NOTE` (`code/code_wait.py:86`).
  - Wait text on the review launch path: `review/review_launch.py:604`.
- Reports that never arrive:
  - Loop alive: `request_round` raises `RuntimeError("the main session wrote no reviewer report within {timeout} s: <files>")`. `run_loop` has no named handler for it; `review_loop_main.main` (`:285`) turns an unlisted `Exception` into `crash_outcome`.
  - Loop gone: `wait_for_step` prints `LOOP_GONE` ("The review loop process is not running, but these reviewer requests have no report:"), `open_request_lines` and the `packet` command (`:190`). `code_wait.print_ended_loop` prints the same heading, `Loop folder:` and the restart step, exit 1.
  - A reviewer that finished with no report: `code_wait.follow_run` prints `NO_REPORT` and the open lines, tells the session to dispatch the agent again with the same prompt, exit 1.
  - Compaction: `gates/waiting_review_launch.py` (SessionStart hook) prints the open dispatch lines for loops of the current branch and a "Left out" line for other branches or detached code-fork loops (`left_out_reason`, `reviewer_dispatch.py:252`).
- `tools/plan_review_reports.py` is a separate check for plan-review files `review-round<k>-shard-<x>.md` (`report_files` `:12`, `missing_rounds` `:19`). It is referenced from `skills/eng-spec/phases/6b-review.md` and not from the review loop.
- The tree has no "round-N exit line" string. The exit lines found are the `ACTION: dispatch-reviewer` block and the `LOOP_GONE` block above.

### 8. Stop file resume line and the `--by` value

- Stop text is written by the session, not by a script. `claude/.claude/skills/code/SKILL.md:26` says a STOP ends with `To go on: /code resume <plan path> <your feedback>` (or without a plan path). `claude/.claude/skills/_shared/review-fork-run.md:27` says a review stop writes `<run folder>/review-stop.md`. A STOP's next-to-last line is `A session that answers adds the line ruled by: <its session name>, or ruled by: user, relayed by <its session name> ...`, and its last line is `To go on: /<skill> resume <your feedback>`. A run that waits on nobody has neither.
- Scripts that handle the line:
  - `code/code_relay.py`: `go_on_line` (`:~58`, first `To go on:` line), `with_resume_path` (`:72`, inserts the repo top after `resume`), `relay` (`:~144`), `user_text_reply`. `GO_ON_PREFIX = "To go on:"`, `RESUME_WORD = "resume"` (`:40-41`).
  - `lib/code_stop_record.py`: `record_stop(session, run_folder, repo_top, go_on)` and `last_stop(session)`.
  - `code/phase_start.py --resume` exits non-zero when a newer relayed stop sits in another run folder; it prints that stop's recorded `To go on:` line.
- `--by` choice:
  - `claude/.claude/skills/_shared/review-fork-run.md:33-34`: pass `--by session` when the resume text has a `ruled by: <session name>` line; `--by user` for any other text; for `ruled by: user, relayed by <name>` pass `--by user --relayed-by <name>` for a `[user only]` ask or a plan-impact question.
  - Scripts: `asks_done_line` (`review/review_fix.py:343`) prints `asks-done --by user ...`. `held_summary_lines` (`review/review_fix_asks.py:854`) prints the user's `--by user --packet <id>` call and a `--by session` retry. `phase_asks.py` accepts only `--by user` (Q3). The ruler of a logged ask is `review_asks.ruler_of_ask` (`review/review_asks.py:247`).
  - No script reads a lane entry to pick the ruler. Lane entries (`lib/lane_entries.py:18`) have the field `reports_to`, set by `tools/lanes.py add --reports-to`. A search of the scripts and skills found no reader of `reports_to` in the review or code code.
  - The user-versus-session decision for `decide --by session` is `plan_check.py owner` (owner `session` or `plan`) through `review/review_fix_plan_impacts.py:84-86`.

### 9. /code resume with feedback or a fix list; the review dispatch decision

- Resume: `claude/.claude/skills/code/SKILL.md:32` ("Resume"). The text after `resume` and an optional absolute plan path is the user's feedback. The run rebuilds its place from `<run folder>/stop.md`, the plan's `## Phase Status`, `git status --short`, `handoff.txt` (`handoff.prev.txt` after a phase start) and `review.out`. SKILL.md lines 38-39 cover feedback, sign-off and `pending sign-off`.
- Phase start on resume: SKILL.md step 3 (line 85) picks `phase_start.py --resume` for a phase that stopped with its Phase Status line unchecked, else plain `phase_start.py`. `phase_start.py` moves `stop.md` to `stop.prev.md`, `handoff.txt` to `handoff.prev.txt` and `loop-dir` to `loop-dir.prev`. It keeps `start.json` when its head is an ancestor of HEAD.
- Review dispatch: SKILL.md step 5 says to run the review for every phase, "a pure move or rename too". The session writes `<run folder>/handoff.txt` and runs `code/code_review_start.py <lane> <plan> <N> <handoff> --base <sha> --detach`, then `code_wait.py review`. No script in `code/` decides to skip the loop. `code_review_start.main` (`code/code_review_start.py:~605`) reads the handoff file (missing file: exit with its path), computes `review_scope`, builds the prompt header (lane, repo, plan, phase, later-phase files, held files, tool-fault line, gate env), and refuses a handoff text that an earlier phase's review read (`record_handoff_phase`).
- The loop's own skip: `first_pass` (`review/review_loop_script.py:956`) plans no reviewer when the header has `no-review`, the review scope has no files, or the status is not `converged` (`:962-964`). `first_round_plan` (`review/review_loop_plan.py:~159`) picks the reviewers by file kind and size.
- `/review` and `/fix` forks resume through `claude/.claude/skills/_shared/review-fork-run.md` ("Resume").
- Tests: `tests/scripts/test_code_review_start.py`, `test_code_wait.py`, `test_code_relay.py`, `test_code_stop_record.py`, `test_phase_start.py`, `test_code_skill_text.py`, `test_code_text.py`, `test_code_context.py`.

### 10. Test patterns

- `tests/scripts/toolkit_paths.py`: exports `CLAUDE_DIR` (honors `TOOLKIT_CLAUDE_DIR`), `SCRIPTS_DIR`, `CODE_DIR`, `REVIEW_DIR`, `LIB_DIR`, `TOOLS_DIR`, `GATES_DIR`, `TELEMETRY_DIR`, `CODE_SKILL_FILE`, `script_in`, `REAL_PLANS_ENABLED`. Importing it also runs `guard_real_ledger()` (a failing `ledger` first on PATH).
- Helper modules in `tests/scripts/`: `fake_ledger.py`, `isolated_state.py` (`isolate_state_root`, sets `HANDBACK_STORE_DIR`), `approval_ask_chain.py` (`accepted_approval_ask_text`), `receipt_repo.py`, `no_code_notes.py`, `stubs.py`, `in_process.py`.
- Fixtures: `tests/scripts/fixtures/packets/review-loop-*.txt` (cap-reached, converged-asks, converged-clean, converged-fixed, critical-blocker, plan-impact), `fixtures/review_ask_pass_notes_report.md`, `fixtures/start_review_script.txt`.
- Loop harness: `ReviewLoopHarness` in `tests/scripts/test_review_loop_script.py:617`. It builds a scratch git repo, a stand-in `claude` (`FAKE_CLAUDE`, `:58`) that answers each call from `scenario.json` by agent key (`code-reviewer`, `coder`, `closure`, `check-finder`, `disposition`) and position, and has these methods:
  - `run_script(scenario, header_extra, ...)` (`:673`)
  - `fake_calls`, `store_rows`, `stored_packet`, `finding_rows`, `usage_rows`, `reset_fake_run`
  - Scenario entries support `result`, `edits`, `edits_when_named`, `outside_edits`, `renames`, `deletes`, `commit_all`, `exit`.
  - Constants: `CLEAN_REVIEW`, `FIX_REVIEW`, `CLOSED`, `FIX_THEN_CLEAN`, `APP_BEFORE`, `APP_FIXED`.
- Multi-round: `tests/scripts/test_review_loop_round_two_fixes.py` (`run_two_rounds`; imports the harness as `loop_tests`); in `test_review_loop_script.py`, `test_a_finding_open_after_round_two_dispatches_no_third_round` (`:1828`) and `test_a_second_round_fix_gets_one_final_read_and_no_coder_after_it` (`:5976`).
- Other loop tests: `test_review_loop_ruled.py`, `_findings.py`, `_scope_guard.py`, `_coder.py`, `_closure.py`, `_named_tests.py`, `_prompt_file.py`; `test_reviewer_dispatch.py`; `test_review_asks.py`; `test_review_fix_ask_ruler.py`; `test_review_fix_plan_impacts.py`; `test_handback.py`; `test_review_clean_status_one_owner.py`; `test_session_registry.py`; `test_human_turn_lookup.py`.
- `test_phase_asks.py` helpers: `ask`, `user_only_ask`, `packet_with`, `StoreCase`, `ScriptRunCase`, `WaitCase`. `test_phase_asks_chain.py` swaps the loop's walk for a stand-in (`STAND_IN_SOURCE`, `run_loop`) so no model call is made.
- Runners: `tests/run.sh`, `tests/lint.sh`, `tests/parallel_tests.py`. Scripts are chosen by env vars, e.g. `REVIEW_LOOP_SCRIPT`, `PHASE_ASKS_SCRIPT`, `REVIEWER_DISPATCH_SCRIPT`.

### Dormant scaffolding on these surfaces

- `PLAN_IMPACT_APPLIED` appears only in `review/handback_store.py` (4 occurrences), with no other file reading it.
- `RETIRED_QUOTE_FLAG` in `lib/ask_outcome_words.py` is read only to refuse the flag (`ruling_relay.pop_relay_options`).
- `tools/plan_review_reports.py` `report_files` and `missing_rounds` have callers only inside that file.
- `lane_entries` field `reports_to` is written by `tools/lanes.py` and has no reader in the review or code scripts.
- `session_registry.row_for_name` has one production caller (`tools/session_pane.py`). `session_subagents_dir` has one outside caller (`code/code_review_start.py`).
- In `phase_asks.py`, `RULABLE_OUTCOMES` limits the words to `accepted` and `rejected`; `HELD` and `APPLIED` (in `lib/ask_outcome_words.py`) are used by `asks-done`, not by `rule`.

## Code References

- `lib/session_registry.py:21,29,44,61,91` — `sessions_dir`, `projects_dir`, `live_session_rows`, `row_for_name`, `session_display_name`
- `lib/human_turn_lookup.py:31,45,113` — `session_id_of_name`, `transcript_of_session`, `verified_human_turn`
- `review/ruling_relay.py:41,86,93` — `pop_relay_options`, `verify_relay`, `record_relay`
- `review/review_fix_asks.py:184,206,220,920` — `asks_done_options`, `verified_fix_relay`, `record_unrecorded_relay`, `command_asks_done`
- `review/review_fix_plan_impacts.py:56,65,99,107` — decide relay
- `review/handback_store.py:96,123,188,210,223,238,645,690` — ruling, relay and phase-ask rows
- `review/phase_asks.py:67,99,124,153,219,253,283,301,327,338` — `phase_asks` command
- `review/review_asks.py:88,226,247,309,353` — outcome words, ruler, logging
- `review/review_loop_intake.py:54` — `take_review`
- `review/review_loop_ruled.py:231,283,313,323,673,703,722,747` — ruled-state mixin
- `review/review_loop_findings.py:424,433,474` — repeat matchers
- `review/review_loop_main.py:115,157,186,259` — `build_loop`, resume iter, `run_loop`, `main`
- `review/review_loop_pass_checks.py:18,34` — pass checks
- `review/review_loop_final_read.py:89-92` — `apply_pending_cap`
- `review/review_loop_script.py:145,146,430,434,554,720,890,932,956` — rounds, outcome, walk, first_pass
- `review/capped_review.py:12,16` — `CAP_REACHED`, `effective_status`
- `review/review_fix.py:343,551,565,608` — asks-done line, cap text, scoped rerun
- `review/reviewer_dispatch.py:75,103,156,180,252` — manifest, wait, dispatch lines, left-out reason
- `code/code_wait.py:504,520,546,561` — reviewer pairs, reports, dispatch lines, follow
- `code/code_relay.py:40-41,72` — resume line handling
- `lib/code_stop_record.py` — `record_stop`, `last_stop`
- `claude/.claude/skills/_shared/review-fork-run.md:27,33-34` — stop lines and the `--by` rule
- `claude/.claude/skills/code/SKILL.md:26,32,85` — stop, resume, phase start and review dispatch
- `tests/scripts/test_review_loop_script.py:58,617,673` — fake claude and harness
- `tests/scripts/toolkit_paths.py:11-28` — path constants

## Patterns Found

- State is stored as rows in per-session JSONL files keyed by session id and repo, plus JSON files under `<git dir>/review-fix/`.
- Loop parts are mixins on `LoopRun` (`RuledFindings`, `ReviewIntake`, `PassChecks`, `FinalRead`, `PartialFixRuns`).
- A loop takes its input from a header-line prompt file, with findings in a JSON file named by the `findings` line.
- Reviewer requests and reports go through files (`reviewer-requests/`); the loop polls and the main session or `code_wait.py` writes the reports.
- A status or reason is a named constant in its owner (`CAP_REACHED`, `*_REASON`).
- Tests run the script as a subprocess against a stand-in `claude` and a scratch git repo, with per-test `HANDBACK_STORE_DIR`.

## Reuse Inventory

- `session_registry.live_session_rows() → list[dict]` — `lib/session_registry.py:44` — live session rows
- `session_registry.row_for_name(name) → dict | None` — `:61` — live row by name
- `session_registry.session_display_name(session_id) → str` — `:91`
- `session_registry.sessions_dir()`, `projects_dir()` — `:21`, `:29`
- `human_turn_lookup.session_id_of_name(session_name) → str` — `lib/human_turn_lookup.py:31`
- `human_turn_lookup.verified_human_turn(session_name, after_epoch) → HumanTurn` — `:113`
- `ruling_relay.pop_relay_options(words) → (rest, RelayRequest | None)` — `review/ruling_relay.py:41`
- `ruling_relay.verify_relay(request, filed_at) → RelayedRuling` — `:86`
- `ruling_relay.record_relay(session_id, repo, relayed, asks)` — `:93`
- `handback_store.record(session_id, kind, **fields)` — `review/handback_store.py`
- `handback_store.rulings(session_id, repo) → Rulings` — `:188`
- `handback_store.record_rejected_ask(...)`, `rejected_ask_rows(session_id, repo)` — `:210`, `:238`
- `handback_store.record_relayed_ruling(...)`, `record_relayed_plan_ruling(...)` — `:223`, `:123`
- `handback_store.unruled_phase_asks(repo)` — `:690`
- `review_asks.parse_outcome_words(words, count, allowed, note_required)` — `review/review_asks.py:88`
- `review_asks.user_only_refusal(asks, ruler, user_command, holdable=False)` — `:226`
- `review_asks.ruler_of_ask(item, call_ruler)` — `:247`
- `review_asks.log_ask_outcome(...)`, `record_rejected_asks(...)` — `:309`, `:353`
- `phase_asks.split_ruler(words)`, `ruler_of_call(words, asks)` — `review/phase_asks.py:253,283`
- `approval_asks_store.read_saved_asks(repo)`, `write_saved_asks(repo, paths, wanted)`, `forget_ruled_approval_paths(repo, asks)`, `check_approval_paths_readable(repo, asks)` — `review/approval_asks_store.py:81,118,189,179`
- `review_loop_findings.repeats_a_rejected_ask(ask, rejected_asks)`, `repeats_an_ask(...)`, `refiles_accepted_drift(text, accepted)` — `review/review_loop_findings.py:424,433,474`
- `capped_review.effective_status(packet, repo)` — `review/capped_review.py:16`
- `reviewer_dispatch.write_round`, `request_round`, `pending_requests`, `all_requests`, `request_lines`, `open_request_lines`, `wait_for_step`, `waiting_launch_lines` — `review/reviewer_dispatch.py:75,103,151,140,156,171,180,265`
- `code_relay.go_on_line(text)`, `with_resume_path(text, repo_top)` — `code/code_relay.py`
- `code_stop_record.record_stop(...)`, `last_stop(session)` — `lib/code_stop_record.py`
- `lib/review_fix_names.py` constants for state file and key names
- `lib/ask_outcome_words.py` constants and `rule_command`, `user_only_numbers`, `user_only_reason`, `rule_instruction`
- `lib/ruled_change_text.py` `changed_text`, `ruled_note`, `is_no_code_ruling`
- Tests: `ReviewLoopHarness`, `FAKE_CLAUDE`, `CLEAN_REVIEW`, `FIX_REVIEW`, `CLOSED` (`tests/scripts/test_review_loop_script.py`); `fake_ledger.install`; `isolated_state.isolate_state_root`; `approval_ask_chain.accepted_approval_ask_text`; `receipt_repo.make_repo` and `plant_receipt`; `toolkit_paths` constants; `tests/scripts/fixtures/packets/*`
