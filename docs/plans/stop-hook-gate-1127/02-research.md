---
date: 2026-11-27
git_commit: be9a5807db3eb2cf771f4c724c1798656c31ef20
branch: fix/stop-hook-keeps-reply
topic: Stop-event hooks, the staged-claim and format gates, shared hook libs, tests, change files and queue items
tags: [hooks, stop, staged_claim_gate, format_changed, tests, change-files, queue]
status: complete
---

# Research: Stop-event hooks and their surroundings

Paths are relative to `/home/brandon/dotfiles-stop-hook-keeps-reply` unless they start with `~`.

## Findings

### Q1. Stop hooks in settings.json

`claude/.claude/settings.json:587-609` (`"Stop"`) holds two groups.

- Group 1 (lines 588-599), two sync commands:
  - `sh ~/.claude/scripts/tools/hook-python ~/.claude/scripts/gates/format_changed.py` (line 592)
  - `sh ~/.claude/scripts/tools/hook-python ~/.claude/scripts/gates/staged_claim_gate.py` (line 596)
- Group 2 (lines 600-608): `~/.claude/scripts/telemetry/ledger-hook stop` with `"async": true` (line 604-605).

Related events:
- `SubagentStop` (lines 568-586): `staged_claim_gate.py` through hook-python (line 573), then `ledger-hook subagent-stop`, async (581-582).
- `StopFailure` (610-619): `ledger-hook stop-failure`, async.
- `format_changed.py` is also registered under `UserPromptSubmit` (line 630).

Which can emit a block decision:
- `staged_claim_gate.py` prints `{"decision": "block", "reason": ...}` (`gates/staged_claim_gate.py:276`).
- `format_changed.py` has no block output. Stop output is none. Its only stdout is the UserPromptSubmit `systemMessage` line (see Q5). It always returns 0 (`gates/format_changed.py:91,101,...`, docstring line 5).
- `ledger-hook` runs `"$ledger" hook "$@"; exit 0` (`telemetry/ledger-hook:30-31`); its header says "a telemetry hook never blocks the session" (line 9). With no ledger it exits 0 (line 27); only `skill-use` and `test-edit` fall back to `hook_local_row.py` (21-25).

### Q2. Stdin and stdout of each Stop hook

`staged_claim_gate.py` (paths in `claude/.claude/scripts/`):
- stdin: `json.load(sys.stdin)` (`gates/staged_claim_gate.py:259`). Fields read: `stop_hook_active` (260), `last_assistant_message` (262), `hook_event_name` (main, after 262), `cwd` and `transcript_path` (`staged_claim_reason`, from 222), and for SubagentStop the fork fields `agent_transcript_path`, `transcript_path`, `agent_id`, `agent_type` (`lib/fork_review.py:190-210`).
- stdout: one line `json.dumps({"decision": "block", "reason": " ".join(found_reasons)})` (`gates/staged_claim_gate.py:276`). No block prints nothing.
- stderr: `staged-claim-gate: <check> skipped: <ErrType>: <msg>` per crashed check (`guarded`, 237-244) and `staged-claim-gate: skipped: ...` for a crash in `main` (`__main__` block, 279).
- exit code: always 0 (fail-open; docstring "Fails open: any error exits 0 with a line on stderr").
- Skip switch: `CLAUDE_SKIP_HOOKS` non-empty skips `main` (`__main__` block).
- `stop_hook_active` true returns with no output.
- Reasons it can join (space-joined): staged claim (index text), `permission_question.REASON` (Stop only), `announced_step.REASON` (Stop only), `fork_review.REASON` (SubagentStop only).

`format_changed.py`:
- stdin: read as bytes, parsed with `hook_input.parse_documents` (`gates/format_changed.py:93-94`); fields `hook_event_name`, `session_id`, `cwd`, `prompt`, `transcript_path` (95-99). `ValueError`/`JqError` returns 0 (100-101).
- stdout: only `code_context.code_start_warning(...)` for UserPromptSubmit (102-105). Stop writes no stdout or stderr from the script itself; it runs formatters (`format_files.run_formatters`, line 156).
- Exit: `sys.exit(main())`, `main` returns 0 on every path.

`ledger-hook stop`: stdin passes through to the external `ledger hook stop`; output is the ledger's. Source of that binary is outside this repo.

Fixtures for Stop events: none captured. Search of `tests/scripts/fixtures/` for stop/hook/event/payload names finds only `hook_event_code_fork_write_stop.json`, `hook_event_session_start_agent.json`, `hook_event_session_start_main.json`. The first is a PreToolUse-shaped `Write` event (`tool_name`, `tool_input`, `agent_type`) to a `stop.md` file, used by `tests/scripts/test_fork_write_scope.py`, not a Stop event. Stop tests build payloads inline (Q8). `tests/scripts/fixtures/subagent_api_error_last_record.json` is a transcript record.

### Q3. How `staged_claim_gate.py` decides to block

Flow (`claude/.claude/scripts/gates/staged_claim_gate.py`):
1. `main` (line 258): load hook JSON; return if `stop_hook_active`; `message = hook["last_assistant_message"] or ""`.
2. `reasons = [guarded("staged_claim_reason", staged_claim_reason, hook, message)]`. On `hook_event_name == "Stop"` also `permission_question_reason`, `announced_step`; on `"SubagentStop"` also `fork_review.missing_review_reason`.
3. `staged_claim_reason`: `claim_sentences(message)`; empty means None. `cwd = hook.get("cwd") or os.getcwd()`. Collect `sentence_problems` per claim sentence. Reason text: "Your message says files are staged, but <problems>. Run `git diff --cached --name-only` in that repo and say what the index holds."
4. `claim_sentences`: `without_quoted_spans(STAGED_CLAIM, message)` drops quoted/backtick spans that hold a whole claim; split with `SENTENCE_END` (`(?<=[.!?])\s+|\n+`); skip a sentence with `NEGATION` (`not|no|nothing|none|never`) or `COMMITTED`; keep it if any `STAGED_CLAIM` match passes `is_index_claim`.
5. `STAGED_CLAIM` regex: `I|I've|I have staged`; `is|are|were|was|now|all|been|left staged`; `remain(s)|stay(s) staged`.
6. `is_index_claim` judges the clause before the match (clauses split by `CLAUSE_BREAK` `[,;:]|\s(and|but|so)\s`). Returns False for: `CONDITIONAL` word in clause; for non-first-person claims: copula after `what|whatever|whichever` (unless `COPULA_BEFORE_QUESTION_WORD`), `OTHER_ACTOR`, `left` with `BARE_ACTOR`, a `lasting` claim whose clause already has `staged`, `REPORTED_SPEECH` not preceded by `I`/`we`. A review-data noun (`rows|records|diffs|findings`) just before the claim in a clause with no `file` word returns False unless the sentence names `index` or `git`.
7. `sentence_problems`: tops = `named_trees` (tree of each existing absolute path and each `git -C <folder>`), else `work_tree_top(cwd)`. For each top, `git diff --cached --name-only` via `script_utils.git_output`. A None result skips the repo. `named` = existing files the sentence names under that top, from the cwd when the cwd is under the top, else from the top. If the index is empty, the sentence names no place, and `session_tree_holds` is True, skip. Empty index gives "the index of <top> holds nothing". Otherwise missing named files give "the index of <top> does not hold <files>".
8. `session_tree_holds`/`session_staging_trees`: trees where the transcript's Bash commands ran `git add` (via `script_utils.bash_commands` and `git_calls.git_calls`, `subcommand == "add"`); passes when such a tree's staged list contains every relative named path that exists in the cwd or that tree.
9. Output: block JSON if any reason (see Q2).

### Q4. Shared lib modules and what each owns

- `lib/hook_input.py`: hook helpers, stdlib plus `import_guard` and `script_utils` (lines 1-14). Owns jq-like readers (`parse_documents` 195, `parse_documents_partial` 210, `jq_str`, `jq_field`, `index`, `jq_get`), `decision_line`/`emit_decision` (PreToolUse permission JSON, 54-64), `emit_stderr` (49), `read_stdin_text` (45), `hook_name` (31), `prune_old_state_files` (180), `cksum` (365), session scratchpad/temp-root helpers, `run_gate` (377: crash gives stderr line and exit 2). Stop users: `format_changed.py` only (lines 29, 38, 94, 128, 129). `staged_claim_gate.py` does not import it.
- `lib/message_text.py`: plain-text helpers for gates reading a final message: `QUOTED_SPAN` (`"..."`, curly, backticks on one line), `BLOCKQUOTE_LINE`, `without_draft_blocks(text)` (drops closed fences via `script_utils.closed_fence_indexes`, and `>` lines), `without_quoted_spans(pattern, text)`. Importers: `staged_claim_gate.py:52`, `announced_step.py:33`, `permission_question.py:47`, `plan_format.py:31`.
- `lib/reply_json.py`: `list_after_last_key(reply, key_pattern)` and `last_json_object(reply, keys)`; reads JSON out of a model reply. Importers: `review/review_loop_findings.py:16`, `review/review_loop_closure.py:11`. Not imported by any Stop hook.
- `lib/api_error_stop.py`: API-error record kind and resume timing (`error_reason`, `reset_epoch`, `record_epoch`; constants `RESET_MARGIN_SECONDS`, `SERVER_ERROR_WAIT_SECONDS`, `MAX_RESUME_AGE_SECONDS`, `MAX_CONSECUTIVE_RESUMES`). Imported only by `tools/lane_status.py:56`. Not by a Stop hook.
- `lib/code_stop_record.py`: per-session `/code` stop record under `~/.claude/code-stop-sessions` (`record_stop`, `last_stop`). Importers: `code/phase_start.py:58`, `code/code_relay.py:34`. Not by a Stop hook.
- `lib/import_guard.py`: `guard(gate_name, module_name)` makes a crash in a gate's imports exit 2; `crash_line`. Importers: `code/coder_gate.py:80`, `gates/quality_check_cap.py:49`, `gates/git_discipline_gate.py:53`, `gates/fork_write_scope.py:33`, `lib/hook_input.py:13`. `staged_claim_gate.py` and `format_changed.py` call no `guard` and use no `import_guard` directly (format_changed does import hook_input, which imports it).
- Imports of `staged_claim_gate.py` (lines 47-52): `announced_step`, `fork_review`, `permission_question`, `script_utils`, `git_calls` (`git_calls`, `joined_directory`), `message_text`. `announced_step.py` and `permission_question.py` live in `gates/` and are reached by `sys.path` including `lib` plus the script directory itself (`sys.path[:0]` adds only `lib`; both modules sit in `gates/`, which is on `sys.path` as the script's own directory).
- Imports of `format_changed.py` (lines 27-30): `code_context`, `format_files`, `hook_input`, `script_utils`.
- `lib/user_prompts.py` (used by `announced_step`): `turn_launched_background` (53), `latest_prompt` (85), `user_words` (80), `starts_turn`.

### Q5. `format_changed.py` output

- Stop: produces no block output and no stdout. It formats files (`format_files.run_formatters(".", snapshot_difference(...))`, line 156) and returns 0.
- UserPromptSubmit: writes a snapshot file `~/.claude/state/format-changed/<session>-<cksum(root)>` (lines 123-139) and, when `code_context.code_start_warning(prompt, transcript_path)` is not None, writes it to stdout (103-105).
- That text (`lib/code_context.py:71-79`): `json.dumps({"systemMessage": "Main session context is <N>k tokens as /code starts, over <limit>k. A run this large reads about twice the cache of a small one. Run /clear, then /code again."}) + "\n"`.
- Stop returns 0 early on: `CLAUDE_SKIP_HOOKS` or `CLAUDE_FORMAT_HOOK_OFF` (90-91); bad payload (100); empty session (106-107); not a repo (115); unfinished operation markers (`OPERATION_MARKERS`, 32-33, 143-144); no snapshot (146-147).

### Q6. Output fields emitted under `gates/` and `lib/`

| Field | Emitter | Event / destination |
|---|---|---|
| `decision` + `reason` | `gates/staged_claim_gate.py` | Stop, SubagentStop; stdout JSON |
| `hookSpecificOutput.permissionDecision` + `permissionDecisionReason` | `lib/hook_input.py:56` (`decision_line`, `emit_decision`) | PreToolUse; stdout |
| `hookSpecificOutput.additionalContext`, `hookEventName: SessionStart` | `gates/waiting_review_launch.py:57`, `gates/emit_orchestration.py:51,54` | SessionStart; stdout |
| `hookSpecificOutput.additionalContext`, `hookEventName: PreToolUse` | `gates/settled_lessons_hook.py:107` | PreToolUse; stdout |
| `hookSpecificOutput.additionalContext`, `hookEventName: PostToolUse` | `gates/batch_reads_nudge.py:118` | PostToolUse; stdout |
| `systemMessage` | `lib/code_context.py:79` | UserPromptSubmit via `format_changed.py:105`; stdout |
| plain stderr lines | `hook_input.emit_stderr` (`stale_citation_gate`, `comment_bloat_gate`, `claudemd_linecount`); `import_guard.crash_line`; `staged_claim_gate` `staged-claim-gate: ...` | stderr; exit 2 for `run_gate` and `import_guard` crashes |

`staged_claim_gate.py` writes `reason` only; no `systemMessage` or `additionalContext`.

### Q7. How the last reply text is obtained

- For Stop and SubagentStop it comes from the hook payload field `last_assistant_message` (`gates/staged_claim_gate.py:262`), a plain string. The scripts do not read it from the transcript. No function under `claude/.claude/scripts` extracts the last assistant text from a transcript; `rg 'def (last_assistant|assistant_text)'` finds none.
- Multi-block messages and tool-use blocks: not handled in these gates; the message is one string. Transcript parsing helpers exist for other uses: `script_utils.transcript_record`, `record_blocks`, `record_tool_calls`, `tool_use_calls`, `bash_commands(transcript_path)` (`lib/script_utils.py:1325`), `last_api_error` (1243). `user_prompts.starts_turn` (`lib/user_prompts.py:36`) treats a `user` record as a turn start unless sidechain, meta, compact summary or tool_result content.
- Quoted and code text: `message_text.QUOTED_SPAN` (`lib/message_text.py`). `staged_claim_gate` calls `without_quoted_spans(STAGED_CLAIM, message)` so only spans whose inner text matches the claim pattern are dropped. `announced_step` calls `without_quoted_spans(ANNOUNCEMENT, without_draft_blocks(message))` (`gates/announced_step.py:83`), so closed fenced blocks and `>` lines are removed first. `permission_question.closing_question` uses `without_quoted_spans(OPENING_QUESTION, message.strip())` on the last `TAIL_CHARACTERS = 400` characters (`gates/permission_question.py:141-155`).
- `staged_claim_gate.py` does not call `without_draft_blocks`: fenced blocks and blockquote lines stay in the text it scans.
- Sentence split: `SENTENCE_END = (?<=[.!?])\s+|\n+` in both `staged_claim_gate.py` and `announced_step.py`.

### Q8. Test patterns

Locating the script: `tests/scripts/toolkit_paths.py` defines `TREE_CLAUDE_DIR` (line 12, the tree the tests sit in), `CLAUDE_DIR` (overridable by `TOOLKIT_CLAUDE_DIR`, 13), `SCRIPTS_DIR`, `GATES_DIR` (= `SCRIPTS_DIR / "gates"`, 21), `TOOLS_DIR`, `LIB_DIR`, etc., plus `script_in(root, name)`.
- `test_staged_claim_gate.py:19`: `SCRIPT = toolkit_paths.GATES_DIR / "staged_claim_gate.py"`.
- `test_format_changed.py:22`: `SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR) / "format_changed.py"`.

`test_staged_claim_gate.py` (793 lines):
- `StagedClaimGateTest.setUp` makes a temp dir, a `repo` (via `make_repo`: git init, commit a.txt/b.txt, then modify both unstaged) and `outside`.
- `run_gate(message, cwd, event="Stop", stop_hook_active, transcript_path, home)` builds `{"hook_event_name", "cwd", "last_assistant_message", "stop_hook_active", "transcript_path"}`, runs `[sys.executable, SCRIPT]` with the JSON on stdin, `cwd=self.tmp`, asserts `(returncode, stderr) == (0, "")`, returns stdout. `assert_blocked` loads the JSON, checks `decision == "block"` and `"git diff --cached --name-only"` in `reason`; `assert_passes` asserts stdout is `""`.
- Cases by phrase form (all `subTest` lists): empty-index claims "The files are staged for you to commit.", "I staged the change.", "All three edits are now staged." (65); SubagentStop (73); index holds files (76); named file missing (81); other repo/tree via path, `git -C`, `~` (87, 93); transcript-vouched linked worktree (110-217); description of the hook, speech reports ("says", "claiming"), (219); quoted claims (228); reporting word with a claim still blocks, incl. "I said I staged the fix." (239); no-claim messages "Nothing is staged yet.", "No files are staged.", "were staged and committed" (270); conditionals "Once...", "After..." (277); "whether" (282); "what is staged" (288, 294, 300); conditional word in earlier/after clause (309-318); review data (324, 331); behavior description (339); other session's work (349, 359, 380, 396, 404); negation in another sentence (410); subdirectory cwd (415); crash isolation per check via `load_gate`/`run_main` with `mock.patch.object` (428-470); non-JSON stdin exit 0 with `staged-claim-gate: skipped:` (471); second stop and outside-repo pass (491).
- Torn/missing transcript cases: 246, 261, 267.
- `PermissionQuestionTest` starts at 496 (also a test of both reasons at 787); other test files for the sibling checks: `test_announced_step.py`, `test_fork_review_gate.py`.

`test_format_changed.py` (419 lines):
- `Repo` helper class (line 29): temp home/bin/repo, fake formatters on PATH that log argv to `FAKE_LOG` (`FAKE_TOOL`, line 25), `git`, `put`, `tool(name, local=False)`, `hook(event, session, cwd, raw, extra_env)` (runs the script with `{"hook_event_name","session_id","cwd"}` JSON and a controlled env), `calls()`.
- `FormatChangedTest` (line 106): selection by extension (142), oxlint/oxfmt/eslint/prettier (128-193), plan files (200), snapshot semantics (208, 237-281), skip switches (262, 304, 310), bad payloads (314), snapshot pruning (320), missing npx (332), empty repo (341), merge/squash/cherry-pick markers (351-406).
- No test covers a `last_assistant_message` or block output for this script.

### Q9. Timing and `hook-python`

- No timing or benchmark harness for hooks exists in `tests/` or `claude/.claude/scripts/` (matches on `bench`/`median`/`timeit`/`perf_counter` are in unrelated files: `tools/capture_packets.py`, `review/review_loop_packet.py`, `test_gate_replay.py`, `gate_replay.py`, etc.). Timing numbers appear in change note `docs/changes/notes/2026-11-01-stop-hook-sends-back-a-closing-permission-question.md` ("30 runs each ... median: bare Python start on an empty file 12.2 ms, master's gate 57.4 ms, this branch's gate 47.3 ms"). Its rig path `~/dev/evals/askstop2/rig/` does not exist on this machine.
- `tests/scripts/gate_replay.py` and `test_gate_replay.py` exist (replay harness; not read in depth).
- `claude/.claude/scripts/tools/hook-python` (sh, 69 lines): `MIN_MINOR=10`, `MAX_MINOR=20` (lines 9-10). Order: (1) pyenv version from `PYENV_VERSION` or `$PYENV_ROOT/version` when its minor >= 10, `exec` that `bin/python3` (26-43); (2) `python3.N` from 20 down to 10 on `PATH`, skipping `*/shims` dirs (45-58); (3) first `python3` on `PATH` outside shims (60-67); (4) `exec python3 "$@"` (69). It only selects an interpreter and execs with the original arguments. `tests/scripts/test_hook_python.py` keeps `MIN_MINOR` equal to `ruff.toml` target-version and checks every settings.json command of form `sh ~/.claude/scripts/tools/hook-python ~/.claude/...py` (`LAUNCHER_PREFIX`, `PYTHON_SCRIPT`, lines 14-16).

### Q10. Change files

- Location: `docs/changes/notes/<YYYY-MM-DD>-<slug>.md` (1297 files under `docs/changes`), plus built pages `index.md`, `what-worked.md`, `ruled-out.md`, `changelog.md`, `in-progress.md`, `fixes-by-script.md`.
- Format (from `~/agent-evals/bin/build_changes.py` docstring, lines 1-110): frontmatter of `key: <JSON value>` lines, then body.
  - Required keys: `type: "Change"`, `title`, `description` (one plain sentence), `generated` ({"by", "at"} with ISO datetime offset whose first 10 chars equal the stem date), `seq` (int >= 1), `components` (ids like `script/staged-claim-gate`; may be empty), `evidence` (at least one), `watches` (list; may be empty), `change_type` (added|changed|removed|fixed|security|deprecated).
  - Optional keys: `kind`, `test`, `asked`, `proof`, `unmeasured`, `overlap`, `regression`, `reverts`, `impact`. `kind` is required for changes dated 2026-10-24 or later.
  - `kind` values from `PROOF_REQUIRED_FROM` (2026-10-25): `fix` (needs `test` as `path::name`), `user-rule` (needs `asked`: "<YYYY-MM-DD>: paraphrase", no quote marks), `structured` and `open` (need `proof`: finding stems whose `task_class` equals the kind and `runs_per_arm` >= 8 for structured, 32 for open). `behavior` is refused from that date.
  - A behavior change (kind behavior, structured or open, dated 2026-10-24 or later) needs non-empty `watches` or non-empty `unmeasured` (a reason no intake metric can read it); `unmeasured` changes are listed in the changelog under "Unmeasured behavior changes". A behavior change that names a watch an earlier change owns, or one on a metric another open watch reads, is refused unless `overlap` holds a reason.
  - `impact`: {"metric": tokens|cost|wall-clock|quality, "before", "after", "unit", "finding", optional "better" for quality}; all-empty means no measured gain.
  - Unknown keys: printed as stderr warnings, never fail the build.
  - Body: level-2 headings `Change`, `Evidence`, `Result`, `Watch`, `Back-out`, in order, each with text (dash allowed).
  - Privacy guard: build refuses on `WORK_TERMS` matches.
  - Commands: `python3 build_changes.py [--root DIR] ... [--check]` and `python3 build_changes.py [--root DIR] new "<title>" --by <actor> [--date YYYY-MM-DD]` (writes an unfilled stub, seq one past the highest on that date, rebuilds nothing).
- Real examples: `docs/changes/notes/2026-10-28-stop-hook-checks-a-staged-claim-against-the-index.md` (kind `fix`, `change_type: "fixed"`, `evidence: ["judgment"]`, `test` set, `unmeasured: ""`, `watches: []`, `seq: 217`) and `docs/changes/notes/2026-11-01-stop-hook-sends-back-a-closing-permission-question.md` (kind `structured`, `evidence: ["bench","tests"]`, two `watches`, `proof` stem, with a `### Ruling 2026-11-15` subsection under Watch).

### Q11. Queue items about Stop hooks (`~/agent-evals/queue/`, 1639 files)

Status is `done` or `dropped` for every item found by name; the search for open/ready/claimed items matching stop/staged text returned no queue item (only non-queue files matched: `QUEUE.md`, `FINDINGS.md`, etc.).
- `stop-hook-blocks-from-ending-main-turns-and-run.md`: kind live-edit, done 2026-10-25 (dotfiles f2f7962). Cites `data-ingest/review-queue.txt`: main session 575 blocks in 5535 turns, 98 turns ended right after a block; subagents 2176 blocks in 4257 runs, 2 ended after a block.
- `a-stop-hook-blocks-a-turn-that-ends-asking.md`: kind bench, dropped 2026-10-30 ("smoke baseline never ended on a question"). Cites `data-ingest/ask-census.txt`: 1,364 of 1,885 turn-final questions were permission questions, about 7,200 minutes of wait.
- `fixture-that-ends-a-turn-on-a-permission-question.md`: kind bench, done 2026-11-01. Cites 539 bare approvals, 2980 wait minutes.
- `ship-the-stop-hook-that-sends-back-a-closing.md`: kind live-edit, done 2026-11-01 (dotfiles master 75a2a6a7). Done-when: check folds into an existing Stop hook, tests in `tests/scripts/`, change file carries the median hook time, an intake metric, and a watch in `edit-watches.json`.
- `stop-hook-staged-claim-check-reads-only-the-main.md`: done 2026-10-30 (change 382).
- `staged-claim-stop-gate-reads-a-description-of.md`: done 2026-10-30 (change 378).
- `staged-claim-gate-checks-only-the-cwd-repo-s-index.md`: done 2026-10-31.
- `stop-hook-blocks-a-required-ask-before-an.md`: chore, done 2026-11-05 (`OUTWARD_STEP` names void, cancel, submit).
- `staged-claim-gate-blocks-questions-about-outward.md`: chore, done 2026-11-05 (ticket, PR, reply, message, Slack questions count as outward).
- `staged-claim-gate-blocks-a-question-about-an.md`: chore, done 2026-11-07 (d1de3385).
- `staged-claim-gate-reads-a-description-of-staging.md`: method, done 2026-11-07 (dotfiles 40f9be17); components `script/staged-claim-gate`.
- `staged-claim-gate-still-blocks-a-question-about-an.md`: chore, done 2026-11-13, `not_dup` regression note ("gate fired again on 2026-11-11").
- `a-formatter-rewrites-plan-markdown-after-write-so.md`: done 2026-10-26 (dotfiles 3d01be3): `format_changed` Stop hook ran prettier on `.md`; now skips `docs/plans/`.
- `turn-end-formatter-reflows-agent-markdown-and.md`: done 2026-11-04 (dotfiles 6249194c): prettier turned a line after a blockquote into part of the quote in `agents/review-loop.md`.
- The `rg` hits on `review-loop-*`, `code-step-*` items concern the review loop's own stop hook and code step stops, not these Stop-event hooks (names only; not read).

## Dormant Scaffolding

- `lib/api_error_stop.py` (all functions) has one production importer, `tools/lane_status.py:56`, and no Stop-hook importer.
- `lib/code_stop_record.py` is imported by `code/phase_start.py:58` and `code/code_relay.py:34` only.
- `lib/reply_json.py` is imported only by two review-loop modules.
- `staged_claim_gate.py` does not use `hook_input.run_gate`, `import_guard.guard` or `hook_input.emit_stderr`; it has its own `guarded` and a bottom-of-file try/except.
- No captured Stop or SubagentStop event fixture exists; the only `hook_event_*` fixtures are the three above.
- `transcript_path` is read by `format_changed.py` (line 99) only for `code_start_warning` on UserPromptSubmit; on Stop it is read and unused. `prompt` likewise.

## Code References

- `claude/.claude/settings.json:568-586` — SubagentStop registrations
- `claude/.claude/settings.json:587-609` — Stop registrations
- `claude/.claude/settings.json:610-619` — StopFailure
- `claude/.claude/scripts/gates/staged_claim_gate.py:1-38` — docstring of the claim grammar
- `claude/.claude/scripts/gates/staged_claim_gate.py:54-90` — regex constants
- `claude/.claude/scripts/gates/staged_claim_gate.py:94-110` — `session_staging_trees`
- `claude/.claude/scripts/gates/staged_claim_gate.py:112,123` — `claim_sentences`, `is_index_claim`
- `claude/.claude/scripts/gates/staged_claim_gate.py:192` — `sentence_problems`
- `claude/.claude/scripts/gates/staged_claim_gate.py:222` — `staged_claim_reason`
- `claude/.claude/scripts/gates/staged_claim_gate.py:237` — `guarded`
- `claude/.claude/scripts/gates/staged_claim_gate.py:247` — `permission_question_reason`
- `claude/.claude/scripts/gates/staged_claim_gate.py:258-276` — `main`; line 279 `__main__` block
- `claude/.claude/scripts/gates/format_changed.py:89-157` — `main`
- `claude/.claude/scripts/gates/permission_question.py:117-120,131-155` — `REASON`, `answers_users_question`, `closing_question`
- `claude/.claude/scripts/gates/announced_step.py:66-69,79-` — `REASON`, `announced_step`
- `claude/.claude/scripts/lib/fork_review.py:190-` — `transcript_path_of`, `missing_review_reason`
- `claude/.claude/scripts/lib/code_context.py:70-79` — `code_start_warning`
- `claude/.claude/scripts/lib/message_text.py` — quote and fence stripping
- `claude/.claude/scripts/tools/hook-python:1-69` — launcher
- `tests/scripts/toolkit_paths.py:12-21` — path constants
- `tests/scripts/test_staged_claim_gate.py:25-63` — harness
- `tests/scripts/test_format_changed.py:29-103` — `Repo` harness
- `docs/changes/notes/2026-10-28-stop-hook-checks-a-staged-claim-against-the-index.md`, `docs/changes/notes/2026-11-01-stop-hook-sends-back-a-closing-permission-question.md` — change-file examples
- `~/agent-evals/bin/build_changes.py:1-110` — change-file spec

## Patterns Found

- Stop gates read the payload as one JSON document with `json.load(sys.stdin)` (staged_claim_gate) or through `hook_input.parse_documents` (format_changed).
- Block output on Stop is `{"decision": "block", "reason": ...}` on stdout with exit 0; crashes use stderr lines and exit 0 (fail-open) in `staged_claim_gate`, versus `run_gate` and `import_guard` exit 2 (fail-closed) in PreToolUse gates.
- One gate script bundles several checks (`staged_claim_gate` + `permission_question` + `announced_step` + `fork_review`), each wrapped by `guarded(name, check, *args)`; reasons are joined with a space.
- Both tests run the script as a subprocess with `sys.executable` and a JSON payload on stdin; `test_staged_claim_gate.py` also loads the module with `importlib.util` for `mock.patch.object` crash tests.
- Test paths come from `toolkit_paths`; `HOOK_SCRIPTS_DIR` overrides the gate folder in `test_format_changed.py`.
- Each sibling check has its own `REASON` constant in its own module.

## Reuse Inventory

- `without_quoted_spans(pattern, text) → str` — `lib/message_text.py` — drop quoted/backtick spans whose inner text matches pattern.
- `without_draft_blocks(text) → str` — `lib/message_text.py` — drop closed fenced blocks and `>` lines.
- `QUOTED_SPAN`, `BLOCKQUOTE_LINE` — `lib/message_text.py` — regexes.
- `script_utils.closed_fence_indexes(lines) → set` — `lib/script_utils.py:121`.
- `script_utils.bash_commands(transcript_path) → list[str]` — `lib/script_utils.py:1325`.
- `script_utils.last_api_error(transcript_path, report_unreadable=False)` — `lib/script_utils.py:1243`.
- `script_utils.git_output(dir, *args)`, `work_tree_top(dir)`, `path_is_under(path, root)`, `transcript_record(line)`, `record_tool_calls(record)`, `makes_own_calls(record)` — `lib/script_utils.py` (used by the gate; definitions not re-read here).
- `git_calls.git_calls(command, cwd)`, `joined_directory(cwd, folder)` — `lib/git_calls.py`.
- `user_prompts.latest_prompt(transcript_path)`, `turn_launched_background(transcript_path)`, `user_words(prompt)` — `lib/user_prompts.py:85,53,80`.
- `permission_question.closing_question(message)`, `answers_users_question(transcript_path)` — `gates/permission_question.py:141,131`.
- `announced_step.announced_step(message, transcript_path=None)` — `gates/announced_step.py:79`.
- `fork_review.missing_review_reason(hook)` — `lib/fork_review.py:199`.
- `hook_input.parse_documents(text)`, `jq_str`, `index`, `emit_stderr(text)`, `run_gate(main)`, `decision_line`, `emit_decision`, `read_stdin_text`, `hook_name`, `cksum`, `prune_old_state_files` — `lib/hook_input.py`.
- `import_guard.guard(gate_name, module_name)`, `crash_line(gate_name, error, before_read=True)` — `lib/import_guard.py:38,29`.
- `code_context.code_start_warning(prompt, transcript_path) → str|None` — `lib/code_context.py:70`.
- `code_stop_record.record_stop/last_stop` — `lib/code_stop_record.py:24,31`.
- `api_error_stop.error_reason/reset_epoch/record_epoch` — `lib/api_error_stop.py:28,42,53`.
- `reply_json.list_after_last_key(reply, key_pattern)`, `last_json_object(reply, keys)` — `lib/reply_json.py`.
- `toolkit_paths.GATES_DIR`, `LIB_DIR`, `TOOLS_DIR`, `CLAUDE_DIR`, `script_in(root, name)` — `tests/scripts/toolkit_paths.py`.
- Test harness pieces: `git(repo, *args)`, `StagedClaimGateTest.run_gate/assert_blocked/assert_passes/make_repo/load_gate/run_main` — `tests/scripts/test_staged_claim_gate.py:21-63,461-490`; `Repo` and `FAKE_TOOL` — `tests/scripts/test_format_changed.py:25-103`.
- Fixtures: `tests/scripts/fixtures/hook_event_*.json`, `subagent_api_error_last_record.json`.
- `build_changes.py new "<title>" --by <actor>` and `--check` — `~/agent-evals/bin/build_changes.py`.
