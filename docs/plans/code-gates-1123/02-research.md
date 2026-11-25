---
date: 2026-11-23
git_commit: 54807befa0b6174b20da85b3472c9b552b8e2e21
branch: fix/code-gates-nov23
topic: Toolkit hook gates (quality-check cap, inline interpreter deny, announced-step stop), the /code fork and hand-back records, and the shared lib owners
tags: [hooks, gates, quality_check_cap, inline_interpreter_hint, staged_claim_gate, code-fork, handback, lib]
status: complete
---

# Research: Toolkit hook gates, /code fork run and hand-back records

Paths are relative to `claude/.claude/scripts/` unless they start with `tests/`. Line numbers were taken from reads in this session; the summary carried some of them across a context break, so treat any that a later edit moved as approximate.

## Findings

### 1. Output-filter detection and rerun redirect in `gates/quality_check_cap.py` (616 lines)

- `OUTPUT_FILTER_START = re.compile("^(tail|head|grep)(" + WS + "|$)")` at `gates/quality_check_cap.py:92`. `TEE_TO_FILE` is at 93. `STDOUT_TO_FILE` (95) matches `>`, `>>`, `1>`, `&>` and not `2>`, a descriptor copy or `/dev/null`. `CUT_MARK = "cut"` at 97. `CUT_DENY_TEXT` at 104-107.
- `CheckStep` namedtuple (117-118): `index norm run_file cwd in_repeat_loop output_saved output_cut redirect_files`.
- Step splitting: `run()` calls `split_command_steps(shell_code(command))` (about 498). Per step: `output_saved = saves_output(...)` and `output_cut = not output_saved and cuts_output(...)` (548-551). Helpers: `piped_step` (230), `saves_output` (237), `cuts_output` (245), `redirect_files` (251; uses `parse_simple_commands`, `redirection_writes_file`, `path_word`), `redirect_failed` (273).
- Record side: `record_runs` (333) skips a step when `step_surely_ran` is false, when `redirect_failed(check)` is true, or when the run gave no result. The record file holds the git state hash line, then `CUT_MARK` if `output_cut`, then `start <ns>`. `recorded_output_was_cut` (226) tests `CUT_MARK in lines[1:]`.
- Deny side (574-586): a recorded run that was not cut gives `DenyError` with `DENY_TEXT`. A recorded cut run with `check.output_saved` on the rerun continues (allowed). A recorded cut run with no saved output gives `DenyError` with `CUT_DENY_TEXT`.
- Imports (52-66): `check_output`, `check_scope`, `hook_input`, `reviewed_tree`, `script_utils`; from `shell_command`: `git_subcommand`, `parse_simple_commands`, `redirection_writes_file`, `split_command_steps`, `path_word`; `shell_code`; `runs_only_after_success`, `step_surely_ran`. `import_guard` is used (fail-closed on import crash).

### 2. Pipe-stage and command-word facilities

- `lib/shell_command.py`: `split_command_steps` (832) returns `(operator, step)` pairs, `|` among the operators. `parse_piped_commands` (282) returns `(words, redirections, piped)` triples, `piped` True when a pipe feeds the command. `parse_simple_commands` (272), `split_simple_commands` (266), `parse_raw_simple_commands` (289), `command_after_wrappers` (632), `resolved_command_words` (704), `step_words` (714), `segment_words` (724), `and_steps` / `and_steps_or_whole` (about 857).
- `lib/shell_command_words.py`: `unquoted_word` (15), `word_names_command` (21), `raw_word_names_command` (26), `command_word_index(raw_words, name)` (35).
- `lib/shell_steps.py`: `step_parts` (32), `runs_only_after_success` (92), `step_runs_in_background` (110), `step_surely_ran` (120), `placed_commands` (145; calls `split_command_steps` at 154).
- `lib/check_scope.py`: `command_check_scope` (607), `step_check_scope` (614; `split_command_steps` at 619), `and_step_scopes`, `runs_whole_check`, `runs_tests` (656), `is_check` (852), `names_cargo_test_target` (868).
- `lib/test_run_output.py:85` `command_without_piped_stages` uses `parse_piped_commands`.
- Other callers of `split_command_steps` / `parse_piped_commands`: `tools/pipe_shell_check.py:41`; `lib/shell_statements.py` (220, 359, 407, 496); `lib/git_calls.py:296`; `lib/criteria_verdict.py:90`; `gates/rg_path_gate.py:90`; `gates/inline_interpreter_hint.py` (61, 73, 84, 125, 149); `gates/git_discipline_gate.py:148`; `gates/quality_check_cap.py`.

### 3. Tests for `quality_check_cap.py`

- `tests/scripts/test_quality_check_cap.py` (920 lines, 112 tests), single class `QualityCheckCapTest` (22).
- `SCRIPT` (16-17) reads `HOOK_SCRIPTS_DIR` or falls back to `toolkit_paths.GATES_DIR`. `DENY_START = "[quality-check-cap] '"` (18), `TICK = 0.03` (19).
- `setUp` (23): temp dir with `home/` and `work/`; state root `home/.claude/state/quality-check` (`self.state_root`).
- Event builders: `fire(event, tool="Bash", command=None, session="s1", cwd=None, env_extra=None, **extra)` builds `{"hook_event_name","tool_name","session_id","cwd","tool_input":{command}}` plus extras (e.g. `agent_id`, `agent_type`, `error`) and runs the script as a subprocess with `PATH`, `HOME`, `TMPDIR` only; PostToolUse events sleep `TICK`. `pre`, `post`, `edit`, `assert_allowed`, `assert_denied`, `state_files`, `run_records`.
- Cut/redirect tests: section "a run whose output was cut by tail, head or grep" at about 727-760 (`test_a_check_piped_to_tail_is_allowed_once_more_redirected_to_a_file` 729, `test_head_and_grep_cut_the_output_too` 741, `test_a_cut_run_still_denies_a_rerun_that_does_not_keep_the_output` 748, `test_a_run_kept_in_a_file_before_the_filter_is_not_cut` 755); failed-redirect tests at 273-314; tail-pipe key tests at 138, 192-196, 540-542, 581-606, 725.
- Related: `tests/scripts/test_check_scope.py`-style tests exist for `lib/check_scope.py`; not read here.

### 4. Inline interpreter deny hook (`gates/inline_interpreter_hint.py`, 230 lines)

- The hook has no tracked-file check and no discovery of files the code writes. It decides on command text only (`rg` for `ls-files`/tracked in `gates/` found nothing in this file). Registered at `claude/.claude/settings.json:346`.
- Decision functions: `INLINE_FLAGS` (31), `INLINE` (32), `ALLOWED` import allow-list (39-42), `runs_stdin_code` (58; uses `shell_command.reads_code_from_stdin`), `unparsed_runs_stdin_code` (69), `part_reads_stdin_code` (81), `split_part_reads_stdin_code` (92), `without_quoted_text` (113), `flags_before_script_run_inline_code` (121), `nested_shell_runs_inline_code` (141), `runs_inline_code` (164), `blocked` (170), `pilot_passes` (181, auto mode and shadow log), `emit_deny` (199), `runs_in_foreground` (204), `main` (212). An exception means exit 0 (fail-open).
- Deny message `TEXT` (46-51): "Inline interpreter runs (python3 -c, node -e, perl -e, manage.py shell -c) and code fed on stdin to a bare interpreter (python3 -, python3 <<'EOF', cat file | python3) are blocked. Do not retry another inline form. Write the code to a script file in your scratchpad directory with the Write tool, then run the file: python3 <file>, node <file>, or python manage.py shell < <file>. A script file may still read data on stdin (python3 <file> <<'EOF'). If the command holds no inline code, run the interpreter step as its own Bash call, apart from any later -c, -e or -r flag."
- `main` also denies uncapped test runs (`memory_cap_scope.uncapped_test_run`, `DENY_TEXT`) and foreground full suites (`memory_cap_scope.foreground_full_suite`, `BACKGROUND_DENY_TEXT`).

### 5. Tests and fixtures for the inline-interpreter gate

- `tests/scripts/test_inline_interpreter_hint.py` (188 lines). `HOOK = toolkit_paths.GATES_DIR / "inline_interpreter_hint.py"` (10). Data tables `DENIED_COMMANDS` (13) and `ALLOWED_COMMANDS` (about 95-157), dicts of name to command string, including `"pipe_into_python_after_a_chain": "cd d && cat x | python3 && echo done"` (30) and `"python_dash_with_heredoc"`.
- `InlineInterpreterHintTest` (160): `reason_for(command)` runs the hook as a subprocess with stdin `{"tool_input":{"command":...}}` (no cwd, no repo, no env) and returns `permissionDecisionReason` or `""`. Tests: `test_inline_and_stdin_code_is_denied` (170), `test_a_script_file_module_or_version_flag_is_allowed` (175), `test_the_deny_names_the_scratchpad_script_and_the_stdin_forms` (180).
- The file has no repo setup, no tracked or untracked files; `rg` for `tracked|ls-files|untracked` in it returns nothing. No `cd <dir> && python3 - <<'EOF'` case with a real directory exists; the `cd d && ...` entry uses a literal nonexistent `d`.
- Other related tests: `test_memory_cap_scope.py`, `gate_replay.py`, `gate_replay_corpus.json`, `test_gate_replay.py`.

### 6. Announced-step stop gate

- `gates/announced_step.py` (59 lines): `ANNOUNCEMENT` (24-29), `CONDITION` (30), `OTHER_ACTOR` (31), `WORK_RUNS` (32-33), `REQUEST_THEN_STEP` (35), `FIRST_PERSON` (37), `SENTENCE_END` (38), `REASON` (40-41), `announced_step(message)` (44-58). It takes message text only and reads no transcript and no tool calls; it imports `message_text.without_quoted_spans`.
- `gates/staged_claim_gate.py` (245 lines): `main` (221) reads `hook["last_assistant_message"]` (225), returns on `stop_hook_active` (223), treats `Stop` as the main session (228), calls `announced_step.announced_step(message)` at 234 and appends `announced_step.REASON`; output is `{"decision":"block","reason":...}`. A SubagentStop event does not run the announced-step check. Registered: Stop `settings.json:573`, SubagentStop `:596`.
- Transcript reads in this gate belong to other checks: `session_staging_trees` (80) uses `script_utils.bash_commands(transcript_path)` (88); `permission_question.answers_users_question` (`gates/permission_question.py:116`) uses `user_prompts.latest_prompt` (`lib/user_prompts.py:36`) only when the message ends on a permission question.
- No code in the gate finds `run_in_background` Bash calls or Agent calls in the final turn. Code elsewhere that does: `lib/loop_transcript.py` (`ASYNC_LAUNCH` 21, `open_launches` 314, `open_dispatches` 367, `agent_finished` 402), `lib/script_utils.py` (`tool_use_calls` 1062, `bash_commands` 1085), `review/open_child_gate.py`, `code/fork_children.py:119`.

### 7. Fixtures and tests for the announced-step gate

- `tests/scripts/test_announced_step.py` (77 lines): runs `staged_claim_gate.py` as a subprocess; `run_gate` payload `{"hook_event_name","cwd","last_assistant_message","stop_hook_active","transcript_path": ""}`. Covers blocks, passes, a second stop and SubagentStop. No transcript, no tool_use events.
- `tests/scripts/test_staged_claim_gate.py`: `StagedClaimGateTest` (21; `setUp` temp dir + git repo with `a.txt`,`b.txt` committed then modified; `make_repo`, `run_gate(message, cwd, event, stop_hook_active, transcript_path, home)`, `assert_blocked`, `assert_passes`, `write_transcript(*commands)` at 134 which writes `{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":...}}]}}` lines). `PermissionQuestionTest` (408) reuses these and has `write_prompts` (user-type entries).
- Event shapes: Bash tool_use only, in those tests. `tests/scripts/fixtures/loop_shell_run_in_background.jsonl` (3 lines) holds a real Bash `run_in_background:true` tool_use, a tool_result with `backgroundTaskId`, and a `queued_command` task-notification attachment; `rg` finds no test referencing it by name (the name search above returned nothing outside the plan folder). Agent-call shapes: `test_handback.py` helpers (see 10), `test_open_child_gate.py`, `test_fork_children.py`, `test_loop_transcript.py`.

### 8. /code fork run end to end

- `code_step.py` does not exist. `skills/code/SKILL.md` (116 lines) and `agents/code-fork.md` describe the run.
- Run folder `<git dir>/code-phase` (`code/code_wait.py` constants 62-86: `PHASE_DIR_NAME`, `PID_FILE`, `HANDOFF_FILE`, `PREVIOUS_HANDOFF_FILE`, `PHASE_RUN_FILE="run.json"`, `LOOP_DIR_FILE`, `PREVIOUS_LOOP_DIR_FILE`, `SCOPE_FILE`, `PREVIOUS_SCOPE_FILE`; `phase_dir_or_none` / `phase_dir` 171-181). Files: `pid`, `handoff.txt`, `handoff.prev.txt`, `run.json`, `loop-dir`, `loop-dir.prev`, `review-scope.json`, `review-scope.prev.json`, `start.json`, `stop.md`, `stop.prev.md`, `review-stop.md`, `review.out`, `handoff-phases.json` (`code_review_start.py:88`), `fix-coder-written.json`.
- Writers:
  - `code/phase_start.py` (289): writes `start.json` via `script_utils.write_text_atomically`; `move_aside` (~172, calls ~236-239) moves `stop.md`, `handoff.txt`, `loop-dir`, `review-scope.json` to `.prev`; flags `--new-run`, `--resume`; `other_run_refusal` uses `code_stop_record.last_stop`; calls `fix_coder_written.clear`.
  - `code/code_review_start.py` (670; `--detach`, `--dry-run`, `--base`, `--scope-file`): needs `CLAUDE_CODE_SESSION_ID`; `agent_id = f"{AGENT_PREFIX}{run_id}"`; loop state dir `script_utils.git_path(repo, "code-step")`; writes `pid`; `handback_hook.record_script_dispatch(session_id, repo)` (644); writes the prompt file, `code_wait.write_phase_run(...)`, `loop-dir`; runs the loop script as a subprocess; prints the packet from `reviewer_dispatch.PACKET_FILE` in the loop folder.
  - `code/code_wait.py` (696): `wait_review`, `plan_impact_notice` (308), `phase_asks_notice` (~330), `held_fault_line`; reads the packet and `review.out`.
  - `code/code_relay.py` (191): reads stop files; imports `stop_file_names`, `code_stop_record`.
  - `review/review_loop_packet.py` `write_handback_rows` (~123-150): `handback_store.record_handback` (`no_reviewer=False`), a `stop` row with `ask_rows`, `handback.record_clean_review(args.session)`; `EMPTY_OUTCOME` (~105-112).
  - Gates for the fork: `gates/fork_write_scope.py` (`GATED_AGENT` code-fork 25, `DENY_TEXT` 28; loads `stop_file_names`, `review_fix_names`); `review/open_child_gate.py:33` `CODE_FORK`, `code_fork_deny_reason` 78; `code/fork_children.py` `is_code_fork` 72; `script_utils.FORK_AGENT_TYPE = "code-fork"` (46). `code/coder_gate.py` is registered on SubagentHandback (`settings.json` 435-439).
  - `lib/code_stop_record.py`: `record_stop`, `last_stop`.

### 9. Hand-back treatment of a code-fork hand-back

- `review/handback_hook.py` `handle_hook` (247-311): line 268 `if kind != "handback" or event.get("agent_type") != REVIEW_LOOP: return None` (`REVIEW_LOOP = "review-loop"` at `review/handback.py:102`). A SubagentHandback from `code-fork` is neither parsed nor stored by this hook. Agent PreToolUse/PostToolUse hooks record only `subagent_type == review-loop` (`handle_dispatch` 219, `handle_dispatch_ran` 232). `record_script_dispatch(session_id, repo_dir, no_review=False)` (241) is called by `code_review_start.py:644` and `review_launch.py:594`.
- What it reads: `step` rows via `loop_steps` (31) to see whether a `reviewer` step ran (291); `claim_no_review` (37) reads the prompt for `loop_transcript.NO_REVIEW_MODE`; `transcript_gates` (181) reads the loop transcript (`open_dispatches`, `dead_reviewers`, `loop_transcript.scan` for the full-check receipt, plan edit, ledger rows). It stores `record_handback(..., no_reviewer=unreviewed or reviewer_dead, unreviewed_fix=...)`.
- `review/handback.py` (840): `STATUSES` (66), `CLEAN_STATUSES = ("converged", DEFERRED)` (68), `PACKET_KEYS` (71; includes `skipped_fp`; entries need `item`, `ENTRY_TEXT_KEYS` 87), `stored_effective_status` (673), `stored_packet` (684), `false_clean_reason` (695), `standing_false_clean_reason` (702; None only with a stored hand-back, gap not `NO_DISPATCH`/`REDISPATCHED`, status in `CLEAN_STATUSES`, `no_reviewer` unset, packet parses, no unruled plan impacts), `clean_handback_since` (727), `unruled_plan_impacts` (737), `session_unruled_plan_impacts` (759), `HeldImpactHandBack` (767), `current_session_held_impact_hand_back` (775), `adopt_settles` (789), `record_clean_review` (798; writes `reviewed_tree.record_reviewed`), `main` (828; `check` and `hook`).
- `review/capped_review.py` (36): `CAP_REACHED`, `DEFERRED`, `effective_status(packet, repo)`.
- `review/handback_store.py` (695): `dispatch_ran` 267, `ran_calls_of` 275, `hand_back_dispatch_rows` 280, `was_recorded` 292, `record` 314, `record_handback` 324, `repo_of_latest_dispatch` 335, `latest` 342, `hand_back_standing` 355, `latest_for_repo` 374, `stored_session_rows` 405, `standing_of` 415, `NO_DISPATCH`/`NO_HANDBACK`/`REDISPATCHED` 439-441, `hand_back_gap` 444, `unreviewed_streak` 458, `ended_on_unreviewed_fix` 471, `hand_back_id` 477, `record_asks_logged` 485, `PHASE_ASKS_OPEN`/`PHASE_ASKS_RULED` 501-502, `record_phase_asks_open` 645, `unruled_phase_asks` 690, `plan_ruled_since` 260, `record_ruled_impact` 96, `STALE_STORE_SECONDS` 7 days (23). Row kinds: `dispatch`, `dispatch-ran`, `dispatch-repo`, `handback`, `stop`, `step`, `rejected`, `unreviewed`, `unreviewed-cap`, `no-review-exempt`, `unchecked-code`, `ledger`, `dead-reviewer`, `plan-ruling`, `asks-logged`, `phase-asks-open`, `phase-asks-ruled`.
- Review ran (verify side): `review/verify_common.py` `review_ran` (192, reads `ledger yield --review-trees`), `review_state` (221, `{"read","ran","reason"[,"coveredByCommitReview"]}`), `full_check_state` (245, `full_check_receipt.latest_receipt`), `branch_review_covers` (286), `BranchCredit` (279), context save/load (260/265).
- Skip reason: no step-skip-reason field in `handback.py`, `handback_store.py` or `verify_common.py`. Related: packet `skipped_fp` list; `code/coder_report.py` `SKIPPED_MARKER="SKIPPED"` (12), `skipped_issues` (124), `issue_marker_lines` (103), whose only callers are `review/review_loop_script.py:658` and `:753`.
- Other callers of `false_clean_reason`: `review/saved_handback.py` (29-69), `review/review_fix.py:632`. `record_clean_review` callers: `review/review_fix_plan_impacts.py` (143, 226), `review_loop_packet.py`.

### 10. Hand-back and verify tests

- `tests/scripts/test_handback.py` (2246): `SCRIPT` from `HANDBACK_SCRIPT` (23); packet builders `packet_text` (41), `json_packet` (48), `ask_packet` (53), constants `CONVERGED`, `CAP_REACHED`, `TWO_ASKS`; `HandbackTestBase` (76; `isolated_state.isolate_state_root`, temp store, `HANDBACK_STORE_DIR`, `run_cli` with `-I`, `dispatch`, `capped_packet_on_a_fresh_repo`); `HookTest` (1208; `event`, `fire`); `ReviewerRequiredTest` (1339); transcript builders `transcript_line` (1595), `coder_step` (1599), `ledger_call` (1609), `refused_logger_result` (1613), `review_scope_run` (1618), `background_reviewer_launch` (1627), `task_notification` (1637); `OneCheckedHandBackTest` (1643; `loop_repo`, `send_hand_back`, `hand_back`, `handback_rows`); `NoReviewExemptionOwnerTest` (2153). No `code-fork` reference in `test_handback.py`, `test_verify_common_review_ran.py` or `test_verify_branch_script.py`.
- `tests/scripts/isolated_state.py` `isolate_state_root(test_case)` (13), `STATE_FOLDER_VARIABLES`. `tests/scripts/receipt_repo.py` `make_repo(test, files=None)` (15), `plant_receipt(repo, result="passed", satisfied=True, finish=True, steps=("npm test",))` (25), `NO_RECEIPT_REASON`.
- `tests/scripts/test_verify_common_review_ran.py` (264): `plant_ledger(directory, body)` (27) writes a stub `ledger`; classes `ReviewRan`, `ReviewStateWithoutLedger`, `ReviewStateWithLedger`, `ReviewStateAfterCommit`, `BusyLedger`; `PLANTED_TREE`, `OTHER_TREE` (23-24).
- `tests/scripts/test_verify_branch_script.py` (2173): `VerifyBranchBase` (157; temp repo, `HOME`, `fake_ledger.install`, stub loggers, `VERIFY_STATE_DIR`, `git`, `write`, `stub_logger`), `PrepTest` (267), `ReviewGateTest` (1261), `OpenAskTest` (1361), `LogTest` (1552), `ReviewLogTest` (1961), `ticket_rows` (1024).
- Run-folder builders: `tests/scripts/test_code_wait.py` (886; `handback_records` 25, `temp_dir` 33, `init_repo` 39, `printed` 43, `patch_projects_and_waits` 50, `WaitReviewTest` 230 builds `<repo>/.git/code-phase` with `pid`, `review.out`, `loop-dir`, packet file); `test_code_review_start.py` (964; `CodeReviewStartTest` 28, `PLAN` at `docs/plans/p/spec.md`, `handoff.txt`, runs with `--base` `--dry-run`); `test_phase_start.py` (642; `PhaseStartTest` 30, `git`, `held_by_rows`); also `test_code_relay.py`, `test_code_stop_record.py`, `test_producer_packets.py`, `test_capture_packets.py`, `test_coder_report.py`, `test_coder_gate.py`.
- Packet fixtures in `tests/scripts/fixtures/packets/`: `review-loop-{plan-impact,critical-blocker,converged-fixed,converged-clean,converged-asks,cap-reached}.txt`, `full-check-{unverified,passed,not-run,failed}.txt`, `coder-{why,plan-impact,behavior}.txt`. Skip reasons in tests come from packet text (`skipped_fp`) and coder report `SKIPPED` markers.

### 11. Shared lib owners and importers

- `lib/stop_file_names.py` (no imports): `STOP_FILE`, `REVIEW_STOP_FILE`, `STOP_FILES`, `PREVIOUS_STOP_FILE`. Importers: `code/code_relay.py`, `code/code_wait.py`, `code/phase_start.py`, `gates/fork_write_scope.py`, `tests/scripts/test_review_launch.py`.
- `lib/review_fix_names.py` (no imports): `REVIEW_FIX_FOLDER`, `STATE_FILE_NAME`, `ASK_FINDINGS_NAME`, `APPROVAL_ASKS_NAME`, `RUN_FOLDER_FINDINGS_NAME`, `PENDING_LAUNCH_KEY`, `CORRECT_OPEN_KEY`, `ASKS_DECIDED_BY_KEY`. Importers: `gates/fork_write_scope.py`; review scripts `approval_asks_store`, `approval_restore`, `review_asks`, `review_blocker_text`, `review_fix_asks`, `review_fix_plan_impacts`, `review_fix`, `review_fix_state`, `review_launch`, `review_loop_partial_fix`, `ruling_relay`; 4 tests.
- `lib/session_registry.py`: `config_dir_override` 13, `sessions_dir` 21, `projects_dir` 29, `session_subagents_dir` 37, `live_session_rows` 44, `row_for_name` 61, `other_live_session_in` 69, `holder_label` 84, `session_display_name` 91. Importers: `code_review_start`, `code_wait`, `phase_start`, `lib/human_turn_lookup`, `review_loop_held`, `review_loop_main`, `tools/lane_status`, `pull_keep_index`, `session_pane`, `sweep_scratchpads`; `test_session_registry.py`.
- `lib/code_stop_record.py`: `stop_record_dir` 15, `stop_record_path` 20, `record_stop` 24, `last_stop` 31. Importers: `code_relay`, `phase_start`, `test_code_relay`, `test_code_stop_record`.
- `lib/loop_transcript.py`: `LoopTranscript` 128, `open_launches`, `open_dispatches`, `agent_finished`, `ASYNC_LAUNCH` 21, `SCOPE_CALL` 55, `SCOPE_ROOT` 56, `agent_meta`, `scan`, `last_coder_step`, `plan_edit_reason`, `packet_ledger_reasons`, `reviewed_repo`, `NO_REVIEW_MODE`. Importers: `code_review_start`, `code_wait`, `fork_children`, `handback_hook`, `handback`, `open_child_gate`, `review_loop_script`, `lane_status`, `test_handback`, `test_loop_transcript`.
- `lib/user_prompts.py`: `prompt_text` 15, `user_words` 31, `latest_prompt` 36. Importers: `gates/git_discipline_gate.py`, `gates/permission_question.py`, `lib/human_turn_lookup.py`.
- `lib/script_utils.py`: `git_path` 547, `repo_root` 625, `work_tree_top` 633, `transcript_tail_lines` 990, `last_transcript_record` 1027, `tool_use_calls` 1062, `bash_commands` 1085, `agent_transcript_path` 1096, `write_text_atomically` 1445, `append_jsonl` 1465, `state_file_path` 1493, `read_jsonl` 1537, `FORK_AGENT_TYPE` 46. Callers: `bash_commands` `staged_claim_gate.py:88`; `tool_use_calls` `fork_children.py:119`, `loop_transcript.py:430`; `last_transcript_record` `lane_status.py:117`, `fork_children.py:143,270`, `loop_transcript.py:459`; `transcript_tail_lines` `batch_reads_nudge.py:55`, `code_context.py:48`; `state_file_path` `verify_common.py:257`, `handback_store.py:62`, `code_wait.py:140`, `settled_lessons_hook.py:72`; `agent_transcript_path` `open_child_gate.py:106`, `handback_hook.py:175`; `git_path` `code_wait.py:173`, `code_review_start.py:637`, `coder_gate.py:190`, `reviewer_dispatch.py:275`, `review_launch.py:570`, `review_fix_state.py:85`, `approval_asks_store.py:41`, `accepted_failures.py:36`, `full_check_receipt.py:48`, `fix_coder_written.py:16`, `refactor_flow.py:312`.
- `lib/worktree_snapshot.py` importers: `phase_start`, `format_files`, `full_check_gate`, `full_check`, `review_loop_held`, `review_loop_plan`, `review_loop_ruled_out`, `review_loop_scope_guard`, `close-branch/fix_diff.py`, tests.
- `lib/import_guard.py` importers: `coder_gate`, `fork_write_scope`, `git_discipline_gate`, `quality_check_cap`, `hook_input`.
- `lib/message_text.py` `without_quoted_spans`: `announced_step.py`, `staged_claim_gate.py`, `permission_question.py`.
- `lib/full_check_receipt.py` (`STARTED`, `STEP`, `FINISHED`, `latest_receipt`, `valid_receipt`, `receipt_problem`); `lib/fix_coder_written.py` `clear(repo)`; `lib/reviewed_tree.py` (`record_reviewed`, `is_reviewed`, `fingerprint`, `reviewed_fingerprint`, `tree_fingerprint`, `shared_record_covers`).

### Dormant scaffolding on these surfaces

- `code_step.py` is named in the question but does not exist.
- `handback_hook.handle_hook` returns None for any SubagentHandback whose `agent_type` is not `review-loop` (`review/handback_hook.py:268`).
- `script_utils.bash_commands` has one production caller (`gates/staged_claim_gate.py:88`).
- No hand-back or verify test references `code-fork`.
- `tests/scripts/fixtures/loop_shell_run_in_background.jsonl` is not named by any test file found.
- `code/coder_report.py` `skipped_issues` has two callers, both in `review/review_loop_script.py`.

## Code References

- `claude/.claude/scripts/gates/quality_check_cap.py:92` — `OUTPUT_FILTER_START`
- `claude/.claude/scripts/gates/quality_check_cap.py:574` — cut/saved deny branch
- `claude/.claude/scripts/gates/inline_interpreter_hint.py:46` — deny `TEXT`
- `claude/.claude/scripts/gates/announced_step.py:44` — `announced_step(message)`
- `claude/.claude/scripts/gates/staged_claim_gate.py:221` — Stop/SubagentStop `main`
- `claude/.claude/scripts/lib/shell_command.py:282` — `parse_piped_commands`
- `claude/.claude/scripts/lib/shell_command.py:832` — `split_command_steps`
- `claude/.claude/scripts/lib/shell_command_words.py:35` — `command_word_index`
- `claude/.claude/scripts/lib/check_scope.py:607` — `command_check_scope`
- `claude/.claude/scripts/review/handback_hook.py:268` — review-loop-only filter
- `claude/.claude/scripts/review/handback.py:68` — `CLEAN_STATUSES`
- `claude/.claude/scripts/review/handback_store.py:324` — `record_handback`
- `claude/.claude/scripts/code/code_review_start.py:644` — `record_script_dispatch`
- `claude/.claude/scripts/code/code_wait.py:62` — run-folder constants
- `claude/.claude/settings.json:346` — inline hook registration
- `tests/scripts/test_quality_check_cap.py:22` — `QualityCheckCapTest`
- `tests/scripts/test_inline_interpreter_hint.py:160` — `InlineInterpreterHintTest`
- `tests/scripts/test_announced_step.py` — announced-step tests
- `tests/scripts/test_handback.py:76` — `HandbackTestBase`

## Patterns Found

- Gate tests run the script as a subprocess with a JSON event on stdin; paths come from `tests/scripts/toolkit_paths.py`, with env overrides (`HOOK_SCRIPTS_DIR`, `HANDBACK_SCRIPT`).
- State is isolated by a temp `HOME` (quality cap) or `isolated_state.isolate_state_root` / `HANDBACK_STORE_DIR` (hand-back).
- Command parsing in gates goes through `lib/shell_command.py`, `shell_steps.py`, `shell_command_words.py`, `shell_statements.shell_code`.
- Hand-back state is per-session JSONL rows in `handback_store.py`; reads go through `hand_back_standing` / `false_clean_reason`.
- Name-only constant modules that import nothing: `stop_file_names.py`, `review_fix_names.py`, `ask_outcome_words.py`.
- Gates state fail-open or fail-closed in comments; `import_guard.guard` gives exit 2 on import crash.

## Reuse Inventory

- `split_command_steps(command) -> [(operator, step)]` — `lib/shell_command.py:832` — split at operators including `|`.
- `parse_piped_commands(...) -> [(words, redirections, piped)]` — `lib/shell_command.py:282` — per-stage words with pipe flag.
- `parse_simple_commands(...)` — `lib/shell_command.py:272` — simple commands with redirections.
- `command_after_wrappers(...)` — `lib/shell_command.py:632` — command past env/nice/timeout wrappers.
- `resolved_command_words`, `step_words`, `segment_words` — `lib/shell_command.py:704,714,724`.
- `command_word_index(raw_words, name)` — `lib/shell_command_words.py:35`; `raw_word_names_command` 26; `word_names_command` 21; `unquoted_word` 15.
- `step_surely_ran`, `runs_only_after_success`, `step_runs_in_background`, `step_parts`, `placed_commands` — `lib/shell_steps.py:120,92,110,32,145`.
- `command_check_scope`, `step_check_scope`, `runs_tests`, `is_check`, `names_cargo_test_target` — `lib/check_scope.py:607,614,656,852,868`.
- `command_without_piped_stages` — `lib/test_run_output.py:85`.
- `shell_code` — `lib/shell_statements.py` — command text with heredocs and comments cut.
- `tool_use_calls`, `bash_commands`, `last_transcript_record`, `transcript_tail_lines`, `agent_transcript_path` — `lib/script_utils.py:1062,1085,1027,990,1096`.
- `open_launches`, `open_dispatches`, `agent_finished`, `scan` — `lib/loop_transcript.py:314,367,402`.
- `latest_prompt(transcript_path)` — `lib/user_prompts.py:36`; `without_quoted_spans` — `lib/message_text.py`.
- `git_path`, `state_file_path`, `write_text_atomically`, `append_jsonl`, `read_jsonl` — `lib/script_utils.py:547,1493,1445,1465,1537`.
- `phase_dir`, `phase_dir_or_none` — `code/code_wait.py:171-181`; `last_stop`, `record_stop` — `lib/code_stop_record.py:31,24`.
- `false_clean_reason`, `record_clean_review`, `CLEAN_STATUSES` — `review/handback.py:695,798,68`; `effective_status` — `review/capped_review.py`.
- `hand_back_standing`, `record_handback`, `hand_back_gap`, `latest_for_repo` — `review/handback_store.py:355,324,444,374`.
- `review_state`, `review_ran`, `branch_review_covers` — `review/verify_common.py:221,192,286`.
- Test helpers: `isolate_state_root(test_case)` `tests/scripts/isolated_state.py:13`; `make_repo`, `plant_receipt` `tests/scripts/receipt_repo.py:15,25`; `plant_ledger` `tests/scripts/test_verify_common_review_ran.py:27`; `fake_ledger.install` (used at `test_verify_branch_script.py` `VerifyBranchBase`); packet builders `packet_text`, `json_packet`, `ask_packet` `tests/scripts/test_handback.py:41,48,53`; transcript builders `transcript_line` etc. `test_handback.py:1595-1637`; `StagedClaimGateTest.write_transcript` `tests/scripts/test_staged_claim_gate.py:134`; `QualityCheckCapTest.fire/pre/post` `tests/scripts/test_quality_check_cap.py`; `tests/scripts/fixtures/packets/*.txt`.
