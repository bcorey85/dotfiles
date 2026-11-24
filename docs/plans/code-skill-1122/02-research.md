---
date: 2026-11-22
git_commit: 8436be97f25cd96ffa9f4ae8c72f37ff32173768
branch: fix/code-skill-nov22
topic: /code skill, code-fork agent, run-folder state, review start, hold logic, review scope, shared fork-run text, rule-meter, tests and consumers
tags: [code-skill, code-fork, review-start, hold-logic, review-scope, rule-meter, tests, opencode]
status: complete
---

# Research: /code skill, code-fork agent, review start, hold logic, review scope, rule-meter, tests and consumers

All paths are relative to the repo root `/home/brandon/dotfiles-code-skill-nov22` unless they start with `~`.
`TK` below means `claude/.claude`.

## Findings

### 1. /code SKILL.md structure

File: `TK/skills/code/SKILL.md`, 161 lines.

Frontmatter (lines 1-8): `name: code`, a `description` that tells the main session to run `python3 ~/.claude/scripts/code/code_relay.py` after the fork hands back (line 3), `context: fork` (4), `agent: code-fork` (5), `model: sonnet` (6), `allowed-tools: [Agent, Bash, Read, Skill]` (7).

Sections, in file order:

- `# Code` (line 10), one sentence: dispatch coder subagent(s) to implement code directly.
- `## Modifiers` (14): `+fast` per `~/.claude/skills/_shared/modifiers.md`.
- `## Instructions` (18), which holds:
  - Preamble paragraphs, each opening with a bold label: End the run only at a STOP (20); The run folder (22); Ending the run hands back (26); Waiting (28); Run notes (30); Resume (32); Plan impacts never stop the run (34).
  - Numbered steps 0-6 (lines 36-98), listed below.
- `## Phase-Complete Block` (100): "Deliver every block through the `brief` skill's shape" (102); `**B - Stop for sign-off**` (104, a fenced template); `**C - Last phase**` (149).
- `## Task` (159): `$ARGUMENTS` (161).

Steps in order:

0. (line 36) No arguments: run `bash ~/.claude/scripts/tools/resolve-task-dir.sh`; exit 0 uses the task directory's `spec.md`, exit 5 the printed plan file, exit 3 starts no run and writes no stop file.
1. (38) Modifiers: `+fast` passes `model: "haiku"`.
2. (40-74) Plan file or pasted plan. `rg -n '^## ' <plan>`, phase-scoped read per `_shared/plan-reading.md`, `lane=eng-spec` when step 0 resolved the input else `lane=code`. Runs `coder_gate.py clear` before the first phase (line 42). Multi-phase bullets: pick the next phase; closing phase runs its named skill (`_shared/closing-phases.md`, line 47); acceptance-criteria file check with a `log-scan scan=acceptance-stub` call (lines 49-51); `- gate:` condition and release evidence; dispatch the coder for one phase; Automated Verification check with a `log-scan scan=prohibition` call (lines 58-60); after `converged` or `deferred`, dispatch a coder to tick the `## Phase Status` line (line 64); the phase-boundary decision, six ordered rules, first match wins (lines 65-71), then "The run never commits and never starts the next phase by itself".
3. (76) Dispatch the coder. Before the dispatch (line 78): `phase_start.py --new-run | --resume | (no flag)`, then `gate_commands.py <plan> <N>`, then `coder_gate.py set <command>...` (skipped when `gate_commands.py` prints nothing). Then (line 79) `coder_packet.py <plan> <N> [--gate-evidence "<who>, <when>: <quoted text>"]`, whose whole output goes in the coder prompt. Line 81: `coder_gate.py clear` when the coder hands back.
4. (83) After the coder completes: put any `PLAN-IMPACT:` block on the phase-end list; summarize.
5. (85-96) Dispatch review. Build the handoff block per `_shared/handoff-block.md`, write it to `<run folder>/handoff.txt`, run `code_review_start.py <lane> <plan path> <N> <run folder>/handoff.txt --base <phase base> --detach` (`--coder-model <model>` when coders run on a model), then `code_wait.py review` again while it prints `Still working`. On `ACTION: dispatch-reviewer` (line 87) dispatch one `Agent` per listed line, then `code_wait.py review <agentId> <report file> ...`. Routes on packet `status`, first match wins (lines 89-96): `critical-blocker` STOP, `cap-reached` STOP, `deferred`, `converged` (uses `phase_asks.py rule`, lines 93-94).
6. (98) Multi-phase plans: settle phase-end plan impacts, run the phase-boundary decision (step 2), print every block with placeholders resolved.

Files the SKILL.md names or defers to (from `rg` over the file, with first line): `_shared/modifiers.md` (16), `_shared/plan-reading.md` (40), `_shared/closing-phases.md` (47), `_shared/handoff-block.md` (85), `brief` skill (102), `/stage` skill (126, 155, 157), `/verify-branch` (57), `scripts/tools/resolve-task-dir.sh` (36), `scripts/code/plan_check.py` (34), `scripts/code/gate_commands.py` (78), `scripts/code/coder_gate.py` (42, 78, 81), `scripts/code/phase_start.py` (78), `scripts/code/coder_packet.py` (79), `scripts/code/code_review_start.py` (85), `scripts/code/code_wait.py` (28, 85, 87), `scripts/code/code_relay.py` (3), `scripts/review/phase_asks.py` (93, 94), `scripts/telemetry/log-scan` (51, 60).

### 2. code-fork agent: definition, launch, subagents

- Definition: `TK/agents/code-fork.md`, 15 lines. Frontmatter: `name: code-fork` (2), `model: sonnet` (4), `disallowedTools: Edit, NotebookEdit` (5). Body (lines 8-15): runs the steps of the skill that started it; never changes a tracked file; applies the user's feedback on the last stop and never raises it again (10-11); on a message that releases a gated phase, quotes it verbatim and names the sender in the coder packet evidence (12-13); on a stop or cancel message, TaskStops every agent it dispatched and ends with a stop naming each agent id (14-15). The frontmatter lists no `tools:` line.
- Launch: three skills set `context: fork` and `agent: code-fork` in frontmatter: `TK/skills/code/SKILL.md:4-5`, `TK/skills/review/SKILL.md:4-5`, `TK/skills/fix/SKILL.md:4-5`. The `code-fork` agent description reads "Started only by those skills; never dispatch it" (`TK/agents/code-fork.md:3`).
- Hand-back to the main session: the `/code` description (`SKILL.md:3`) tells the main session to run `code_relay.py` after the fork returns (see question 4).
- Write scope: `TK/scripts/gates/fork_write_scope.py` is a PreToolUse hook on `Write` (matcher at `TK/settings.json:478`, command at 482). `GATED_AGENT = "code-fork"` (`fork_write_scope.py:25`). The module docstring says the fork writes only files inside a run folder; it is fail-closed for code-fork and fail-open otherwise (lines 12-13, 138-139). `FORK_AGENT_TYPE = "code-fork"` is in `TK/scripts/lib/script_utils.py:33`; `CODE_FORK = "code-fork"` is in `TK/scripts/review/open_child_gate.py:33`.
- Subagents the fork dispatches, as written in the skill text:
  - `/code`: `coder` (`SKILL.md:76`, one coder per phase; two in parallel only for two deliverables that share nothing); reviewer agents when the packet prints `ACTION: dispatch-reviewer` (`SKILL.md:87`: one `Agent` per listed line, `subagent_type` its agent, no `model`); `coder` again for the Phase Status tick (`SKILL.md:64`) and for plan-deviation lines; the closing-phase skill via the Skill tool (`SKILL.md:47`).
  - `/review` and `/fix`: reviewers listed by `ACTION: dispatch-reviewer`; `coder` for `show-plan-impacts` and Plan Deviations lines (`TK/skills/_shared/review-fork-run.md:13`).
  - Reviewer agent definitions in `TK/agents/`: `code-reviewer.md`, `test-reviewer.md`, `test-intent-reviewer.md`, `smell-reviewer.md`, `complexity-reviewer.md`, `plan-reviewer.md`. `REVIEWERS_MAIN` is imported by `code_review_start.py` (used at line 421 of that file) to pick the reviewer set.
- Tool access: `/code` `allowed-tools: [Agent, Bash, Read, Skill]` (`SKILL.md:7`); `/review` and `/fix` `allowed-tools: [Agent, Bash, Read]` (`review/SKILL.md:7`, `fix/SKILL.md:7`).

### 3. Coder dispatch from a code fork and its state records

Coder definition: `TK/agents/coder.md`: `model: sonnet`, `tools: Bash, Read, Edit, Write, LSP`, `skills: [coder-core]` (lines 4-8). The description names its dispatchers: "/code, /refactor, /deps and the review loop" (line 3).

Dispatch sequence per phase (from `SKILL.md:76-81`):

1. `phase_start.py` writes `<run folder>/start.json` (question 5).
2. `gate_commands.py <plan> <N>` prints the phase's gate commands; `coder_gate.py set <command>...` stores the hand-back gate.
3. `coder_packet.py <plan> <N>` prints the coder packet (phase-scoped plan text, cited sections, imported files, optional gate evidence). Usage string: `coder_packet.py <plan> <phase number> [--gate-evidence "<text>"]` (`TK/scripts/code/coder_packet.py:21`).
4. The fork calls `Agent` for the `coder`, then `code_wait.py agent <agentId>` until it stops printing `Still working` (`SKILL.md:28`; `code_wait.py` `wait_agent`, line 399).
5. `coder_gate.py clear` when the coder hands back (`SKILL.md:81`).

State records:

- Coder gate file: `CODER_GATE_FILE = "coder-gate.json"` (`TK/scripts/code/coder_gate.py:112`), path through `gate_path(cwd)` = `script_utils.git_path(cwd, CODER_GATE_FILE)` (line 180-181), so `<git dir>/coder-gate.json`. `set_gate` (line 258) writes `{"repoRoot", "commands", "env", "setAt", "coders": {}}` atomically (line 289-290) and refuses commands that run a whole suite (lines 267-281). `clear_gate` at line 316; `print_gate_summary` at 299.
- Session pointer: `SESSION_POINTER_DIR = ".claude/coder-gate-sessions"` (line 114). `write_session_pointer(session_id, gate_file)` (193) stores `{"gateFile": <resolved path>}`; `read_session_pointer` (200); `remove_session_pointer` (214); `hook_gate_file(event)` (225) returns the pointed file, `None` when the pointed file is gone, and the cwd's gate when there is no usable pointer.
- Gate log: `GATE_LOG = ~/.claude/coder-gate.jsonl` (line 110); rows by `append_gate_log` (693) and `log_gate_run` (703).
- Hooks that read the gate: `settings.json:446` runs `coder_gate.py hook` on matcher `SubagentHandback` (442); `settings.json:379` runs `coder_gate.py bash-hook` on a `Bash` matcher (354). `run_hook` (`coder_gate.py:784`) returns at once unless `event["agent_type"] == "coder"`; `run_bash_hook` (815) likewise, and denies a whole-package command via `whole_package_reason`.
- Gate limits: `MAX_DENIES = 3` (95), `MAX_GATE_AGE_SECONDS = 6 * 3600` (98), `COMMAND_TIMEOUT_SECONDS = 1200` (99), `HOOK_TIMEOUT_SECONDS = 3600` (102).
- Coder report parsing: `TK/scripts/code/coder_report.py` (`open_questions`, `plan_impact_block`, `has_plan_impact_block`, `recommends_eng_spec`, `why_by_file`, `skipped_issues`, `behavior_lines`).
- Review-loop hand-back store (per session): `TK/scripts/review/handback_store.py`. `store_dir()` (line 55) is `$HANDBACK_STORE_DIR` or `~/.claude/state/handback`; `session_file(session_id)` (60) gives `<store>/<session>.jsonl`; `record(session_id, kind, **fields)` (307); `record_handback` (317). Row kinds named as constants: `DISPATCH_RAN = "dispatch-ran"` (33), `PLAN_RULING` (34), `PLAN_IMPACT_RULED` (36), `ASK_REJECTED` (41), `ASK_REJECTION_WITHDRAWN` (43), `ASKS_LOGGED_ROW` (44), `ASK_RULING_RELAYED` (47), `PLAN_RULING_RELAYED` (50), `DISPATCH_REPO_KIND = "dispatch-repo"` (52), `PHASE_ASKS_OPEN` / `PHASE_ASKS_RULED` (494-495). `"dispatch"` and `"step"` rows are written by `TK/scripts/review/handback_hook.py` `handle_dispatch` (line 219) and `record_script_dispatch` (241).
- Hand-back hooks in `settings.json`: PostToolUse `Agent` runs `handback.py hook ran` (line 254-262); PreToolUse `Agent` runs `handback.py hook dispatch` (a matcher `Agent` group near 424); `SubagentHandback` runs `handback.py hook handback` and `open_child_gate.py` (lines 442-457).
- Run-folder files the fork's SKILL steps use (all under `<git dir>/code-phase`): `handoff.txt`, `stop.md`, `start.json`, `pid`, `review.out`, `run.json`, `loop-dir`, `review-scope.json`, `handoff-phases.json`, `relayed`, `bounced`; and `handoff.prev.txt`, `stop.prev.md`, `loop-dir.prev` after `phase_start.py`. Constants: `TK/scripts/code/code_wait.py:70-77`, `TK/scripts/lib/stop_file_names.py:4-9`, `TK/scripts/code/code_review_start.py:73,193`, `TK/scripts/code/code_relay.py:38-39`.

### 4. Stop-event handling

Two things carry the name "stop": the fork's own stop file (a convention of the /code, /review and /fix run) and Claude Code's Stop-family hook events.

Fork stop files:

- Names: `STOP_FILE = "stop.md"`, `REVIEW_STOP_FILE = "review-stop.md"`, `STOP_FILES = (STOP_FILE, REVIEW_STOP_FILE)`, `PREVIOUS_STOP_FILE = "stop.prev.md"` (`TK/scripts/lib/stop_file_names.py:4-9`).
- Written by the fork with the Write tool: `/code` writes `stop.md` (`SKILL.md:26`); `/review` and `/fix` write `review-stop.md` (`TK/skills/_shared/review-fork-run.md:17`).
- Write gate: `fork_write_scope.py` denies a code-fork Write outside a run folder (`settings.json:478-482`). Line 73 of that file compares the resolved name with `stop_file_names.REVIEW_STOP_FILE` and the parent folder name with `RUN_FOLDER_NAME`; `pending_launch_reason` (67) and `review_fix_route_reason` (92) deny `review-stop.md` while a launch is pending.
- Relay: `TK/scripts/code/code_relay.py` (191 lines) prints the newest stop for the main session between USER TEXT markers. Functions: `newest_stop(folder)` (55), `go_on_line(text)` (64), `with_resume_path` (72), `edited_after_clean_review(repo)` (92), `is_stamped` (119), `user_text_reply` (123), `relay_bounced_stop` (133), `relay(repo)` (146), `main(argv)` (182). Constants: `RELAYED_FILE = "relayed"`, `BOUNCED_FILE = "bounced"`, `GO_ON_PREFIX = "To go on:"`, `RESUME_WORD = "resume"`, `RULE`, `FINISHED_RULE`, `RE_REVIEW_FEEDBACK`, `RE_REVIEW_RULE`, `UNREVIEWED_NOTE`, `FALLBACK` (lines 38-52). It exits 1 when there is no stop file (151), when the newest is `stop.prev.md` with no new stop (156), or when the stop was already relayed (162). Its docstring (lines 14-18) says a stop that waits on the user, in a tree changed after the converged review, is "bounced" back through its `To go on:` line.
- Stop record per session: `TK/scripts/lib/code_stop_record.py` (`STOP_RECORD_DIR = ".claude/code-stop-sessions"`, `RECORD_KEYS = ("runFolder", "repoTop", "goOn", "time")`; `record_stop` line 24, `last_stop` line 31). `code_relay.py:142` and `:178` write it; `phase_start.py:137` reads it (`other_run_refusal`, line 130).
- Open-child gate: `TK/scripts/review/open_child_gate.py` (PreToolUse `SubagentHandback`, `settings.json:442-457`) denies a code-fork hand-back while a background launch has not reported back (docstring line 10).

Claude Code Stop-family hooks in `TK/settings.json`:

- `Stop` (line 594): `gates/format_changed.py`, `gates/staged_claim_gate.py`, `telemetry/ledger-hook stop` (async).
- `SubagentStop` (575): `gates/staged_claim_gate.py`, `telemetry/ledger-hook subagent-stop`.
- `StopFailure` (617): `telemetry/ledger-hook stop-failure`.
- `SessionEnd` (565): `telemetry/ledger-hook session-end`.
- `Notification` (225) with matchers `idle_prompt`, `permission_prompt`, `task_complete` (227, 236, 245).
- No Stop-family hook in `settings.json` calls `code_relay.py`; the only invocation is the skill descriptions (`/code` `SKILL.md:3`; the review and fix skills per `tests/scripts/test_guidance_rules.py:174-178`).
- Repo-level stop handling elsewhere: `scripts/.local/bin/herdr-wake-limited` (described in the root `CLAUDE.md` install list) presses Enter on usage-limit stops.

### 5. What the code-run start scripts store at phase start

Two scripts run at phase start.

`phase_start.py` (`TK/scripts/code/phase_start.py`, 198 lines):

- Writes `<run folder>/start.json` (`START_FILE = "start.json"`, line 38) with `{"head": <sha>, "dirty": {<path>: <hash>}}` (`start_record`, lines 46-56: `head` from `script_utils.head_commit`, `dirty` = `file_hash` for each path in `worktree_snapshot.status_codes`). Written atomically with `json.dumps(record, indent=2)` (line 195, in `main`). The run folder is `code_wait.phase_dir(repo)`, i.e. `<git dir>/code-phase`.
- Prints the head sha on stdout; the SKILL keeps it as the phase base.
- Flags `--new-run` and `--resume` (`main`, line 150); unknown arguments exit with usage.
- With no flag, a kept record with the same head is left as it is (line 190-192); `--new-run` or a moved head replaces it. With `--resume` a kept head that is an ancestor of HEAD is printed and the record is kept (`resume_base`, line 118).
- Moves files aside before writing (`move_aside`, line 103): `stop.md` to `stop.prev.md`, `handoff.txt` to `handoff.prev.txt`, `loop-dir` to `loop-dir.prev` (lines 167-169).
- `--resume` refuses when the run folder has no stop of its own and the session's last recorded stop is in another run folder (`other_run_refusal`, line 130).
- `read_start_record` (58) raises `StartRecordError` on a record that does not parse; `main` replaces a bad record with a stderr note (lines 175-180). `unchanged_dirty_files` (83) returns the recorded dirty paths whose bytes are unchanged now, `None` when there is no record, and raises when the recorded head and the base are unrelated (`base_relates_to_head`, line 73).

`code_review_start.py` (`TK/scripts/code/code_review_start.py`, 444 lines), at the review start (step 5, not the coder dispatch):

- `--detach` mode writes `<run folder>/review-scope.json` (`SCOPE_FILE = "review-scope.json"`, line 193; written in `detach`, line 285 on, atomically with `json.dumps(scope._asdict())`), `<run folder>/pid` (`PID_FILE`, `pid_file.write_text(str(loop.pid))`), `<run folder>/review.out` (`REVIEW_OUTPUT`, the child's stdout and stderr), and removes `<run folder>/loop-dir` before launch. It refuses when `running_review_pid(repo)` is not None.
- Every non-dry run records `<run folder>/handoff-phases.json` (`HANDOFF_PHASES_FILE`, line 73; `record_handoff_phase`, line 332): `{"<sha256 of handoff text>": "<plan>#<phase>"}`. It returns the earlier phase when the same text was read for another phase of the same plan, and `main` then exits naming `handoff.txt` and the recovery (lines 396-403). A dry run records nothing.
- A foreground (non-detached) run: `handback_hook.record_script_dispatch(session_id, repo)` writes a `dispatch` row into the handback store (`main`, near line 422); `code_wait.write_phase_run(repo, lane, phase, prompt_file.parent)` writes `<run folder>/run.json` (the lane, phase and `loop_dir`, `code_wait.py:195`); `<run folder>/loop-dir` holds the loop folder path; `write_script_prompt` writes the prompt file and a log under `<git dir>/code-step/` (`state_dir = script_utils.git_path(repo, "code-step")`).
- `<run folder>/handoff.txt` is read, not written, by this script (written by the fork).

### 6. Hold logic and where it is used

Meaning: a "held" file is dirty in a shared work tree and belongs to another live session, not to the run.

Start-time half (which files are held), in `code_review_start.py`:

- `phase_held_files(repo, base_commit, plan, phase, notes)` (line 148) returns holder rows `{"path", "session", "claim"}`. Steps: `phase_start.unchanged_dirty_files` gives files dirty at the run start with the same bytes now; `earlier_phase_files` (133, through `expected_red.earlier_phase_paths`) removes files an earlier phase of the plan names; `CLAUDE_CODE_SESSION_ID` must be set; `session_registry.other_live_session_in(repo, own_session_id)` must return a row. With no start record it holds nothing and notes it on stderr and in `notes`; with no session id it holds nothing and notes it; with no other live session it holds nothing (lines 154-176).
- Claim text: `f"dirty at the run start, unchanged now; live session in {holder['cwd']}"` (line 174).
- Holder labels: `session_registry.holder_label(row)` (`TK/scripts/lib/session_registry.py:69`); tests show it names by name, then session id, then pid (`tests/scripts/test_session_registry.py:26`).
- Liveness: `session_registry.other_live_session_in(folder, own_session_id)` (54) and `live_session_rows()` (37).
- The rows go into the review prompt header as a `held files: ...` line and a `held-by: <json>` line (checked in `tests/scripts/test_phase_start.py:211-229`); `review_prompt` (line 236) takes `holders`.

Loop-time half, `TK/scripts/review/review_loop_held.py` (141 lines):

- `run_held_files(repo, caller_held, only_files)` (18): caller's held set, plus every other dirty file when the run is scoped to `only_files`.
- `implicit_holders(repo, held_files, known_holders, only_files, own_session_id)` (28): rows for files held only through scoping, when another live session works in the repo.
- `caller_holders(caller_held, held_by)` (95): row per caller-named held path, defaulting to `holder_row(path, "the caller", "named held by the caller")`.
- `held_path_in_repo` (45), `names_held_file` (55), `tail_names_held_file` (63), `held_path_of(item, held, owned, repo)` (70): match a finding's path to a held file (exact when the path is a file in the repo; otherwise a tail of exactly one held file and no owned file).
- `split_held_findings(items, held, owned, repo)` (83) returns `(kept, held_items)` and records nothing.
- `skip_held_items(items, held, owned, held_unfixed, repo, holders)` (108): an item on a held file with a holder row goes once into `held_unfixed` as `{"item", "reason"}` with reason `held by <session>: <claim>` (`held_reason`, 104); an item on a held file with no holder row stays with the coder's items.
- `digests` (128) and `note_changed` (134): `file_hash` of each held file before a coder call, then a note in `HELD_FAULTS` (line 15) for each whose bytes changed. The module never writes a held file back.

Use sites (from `rg`):

- `TK/scripts/review/review_loop_main.py:150-153`: `loop.held_files = review_loop_held.run_held_files(...)`, `loop.held_holders = review_loop_held.caller_holders(...)`, `loop.held_holders.update(review_loop_held.implicit_holders(...))`.
- `TK/scripts/review/review_loop_script.py`: `import review_loop_held` (76); `self.held_holders, self.held_unfixed = {}, []` (390); `skip_held_items` call (492-493); `split_held_findings` for nits (502); `"held_unfixed": self.held_unfixed` in the packet outcome (843).
- `TK/scripts/review/review_loop_coder.py`: `HELD_FAULTS` added to the faults list (22); `digests` before a coder call (105); `note_changed` after (127).
- `TK/scripts/review/review_loop_ruled_out.py:45` calls `held_path_of(item, ruled_out, set(), repo)`.
- `held_path_in_repo` imported by `review_loop_signoffs.py:14`, `review_loop_docs_kind.py:13`; `names_held_file` imported by `review_loop_ruled.py:35` and `review_loop_fix_induced.py:9`.
- Packet side: `held_unfixed` in `handback.py` (`SCRIPT_PACKET_KEYS` line 77, `LIST_KEYS` line 80, `ENTRY_TEXT_KEYS` line 86, `held_unfixed_text` 628, rendered "Unfixed, held by another session" at 648-650) and in `review_loop_packet.py` (74, 105).
- Handoff text: `TK/skills/_shared/handoff-block.md:28` says `code_review_start.py` replaces `files` with git's changed paths less the held files.

### 7. How the review scope gets built from the work tree

`ReviewScope` (`code_review_start.py:180`): `NamedTuple(holders, handoff, phase_changed, review_base, notes=())`.

`review_scope(repo, base, coder_handoff, plan, phase)` (line 217):

1. `base_commit = script_utils.git_output(repo, "rev-parse", "--verify", f"{base}^{{commit}}")`. When it is not a commit: exits when the handoff has a `  files:` line (`HANDOFF_FILES_LINE`, line 79); otherwise returns `ReviewScope([], coder_handoff, [], None)`.
2. `holders = phase_held_files(repo, base_commit, plan, phase, notes)` (question 6); `held_paths` is their paths.
3. `review_base = diff_base(repo, base_commit)` (line 205): `merge_free_base.merge_free_base(repo, base_commit)`; a merge that does not fold cleanly exits naming it (`MergeConflictError`), and a git failure exits with `MergeBaseGitError`'s text.
4. `handoff = handoff_with_git_files(repo, review_base, coder_handoff, held_paths, plan)` (line 101): finds the `  files:` line, keeps the coder's `why:` blocks by path (`coder_why_blocks`, 83), takes `coder_gate.changed_files(repo, base_commit)` less held paths (`script_utils.without_paths`), then drops files under the plan's folder (`plan_format.outside_plan_folder`), and builds entries with `handoff_files.file_entry_lines(changed, {}, "changed since the phase base", why_by_path)`. With no changed file it writes `  files: []`.
5. `phase_changed = phase_changed_files(repo, review_base, held_paths)` (128): `script_utils.changed_files(repo, base_commit)` less held paths.
6. Returns `ReviewScope(holders, handoff, phase_changed, review_base, notes)`.

Lower-level pieces the scope uses:

- Work-tree change set: `script_utils.changed_files(directory, base="HEAD", with_deleted=False)` (`TK/scripts/lib/script_utils.py:491`).
- Merge-free base: `TK/scripts/lib/merge_free_base.py` `merge_free_base(repo, base)` (84), with `merge_commits` (33), `merged_in_parents` (42), `conflicted_paths` (50), `fold_parent` (61); builds a synthetic base commit with `git merge-tree --write-tree` (`GIT_VERSION_NEED`, line 13; `GIT_USER` line 11).
- Work-tree snapshot: `TK/scripts/lib/worktree_snapshot.py`: `status_entries(root)` (24), `status_codes(root)` (47), `staged_paths(root)` (52), `file_hash(root, path)` (57), `working_tree_changes(root)` (69), `work_tree_tree(repo)` (111), `take(repo)` (129), `changes_since(before)` (141); `UNTRACKED = "??"`, `UNREADABLE = "unreadable"`, `RENAME_CODES`, `CHANGE_KINDS = ("changed", "rewrote_edited", "created")`.
- Fingerprints for the reviewed tree: `TK/scripts/lib/reviewed_tree.py` `tree_fingerprint(top, base="HEAD", exclude_rel=None, ...)` (84), `work_tree_fingerprint(repo, log=None)` (214), `reviewed_fingerprint(repo_dir, base="HEAD")` (251), `record_reviewed(session, repo_dir, tree=None)` (358), `is_reviewed` (380), `push_review_state(repo_dir)` (318) with `PUSH_NO_RECORD`/`PUSH_REVIEWED`/`PUSH_CHANGED` (50-52).
- Notes paths left out of the fingerprint: `TK/scripts/lib/notes_paths.py`: `committed_notes_list(top, timeout=None)` (50), `is_notes_path(path, declared_paths)` (69), `exclude_pathspecs(declared_paths)` (78), `matches_notes_entry` (62), `notes_entries` (26), `notes_entry_error` (32), `notes_list_errors` (40), `committed_list` (21); `DOCS_FOLDER = "docs/"`, `NOTES_SUFFIX = ".md"`, `NOTES_PATHS_FILE = ".claude/notes-paths"` (11-14).
- The loop's own dirty-file read: `review_loop_plan.scope(repo)` (called at `review_loop_held.py:23`); `TK/scripts/review/review_loop_plan.py` is 218 lines.
- Scope handoff to the detached child: parent writes `review-scope.json`, child reads it with `read_scope` (line 196) through `run_scope` (368) after `--scope-file` (`SCOPE_FILE_FLAG`, line 191); `read_scope` exits on a file that is not the 5-field object.
- The scope also feeds `review_prompt(repo, lane, plan, phase, handoff, phase_changed, holders, review_base, coder_model)` (236) and `phase_gate_commands(repo, plan, phase, base, handoff)` (265), where `scope.review_base or base` is the base given.

### 8. `_shared/review-fork-run.md`

`TK/skills/_shared/review-fork-run.md`, 19 lines. Heading `# The /review and /fix fork run` (line 1). Paragraphs, each with a bold label:

- The run folder (3): `git rev-parse --path-format=absolute --git-path code-phase`; the fork writes only `<run folder>/review-handoff.txt`, `<run folder>/fix-findings.md` and `<run folder>/review-stop.md` with the Write tool.
- Launch (5): run the skill's launch line with `--detach` in the foreground, then `code_wait.py review --loop <loop dir>` while it prints `Still working`.
- Reviewers (7): on `ACTION: dispatch-reviewer`, one `Agent` per listed line, prompt `Read <prompt file> whole and do that task.`, then `code_wait.py review --loop <loop dir> <agentId> <report file> ...`.
- The packet's ACTION lines (9) with bullets 11-15: present-and-wait is a STOP; launch lines run with `--detach`; `show-plan-impacts` or Plan Deviations lines dispatch one `coder` then `code_wait.py agent <agentId>`; `redispatch` and `launch-fix-run`; asks the fork may decide itself run `asks-done --by session`.
- Ending the run hands back (17): final text written to `<run folder>/review-stop.md`; carries the packet's USER TEXT block; the last lines are `A session that answers adds the line ruled by: <its session name>...` and `To go on: /<skill> resume <your feedback>`.
- Resume (19): task text starting `resume` is the reply to `review-stop.md`; passes `--by session`, `--by user`, or `--by user --relayed-by <session name> --quote "<words>"` to `asks-done`, `asks-done --correct` and `decide`.

Referenced by (production files):

- `TK/skills/review/SKILL.md:14`: "Read `~/.claude/skills/_shared/review-fork-run.md` whole first and follow it."
- `TK/skills/fix/SKILL.md:14`: same sentence.
- No other file under `TK` or `opencode` names it (`rg` over both).

Referenced by (non-production):

- `tests/scripts/test_guidance_rules.py:179` reads it through `guidance_text("skills/_shared/review-fork-run.md")` and asserts `<run folder>/review-stop.md`, `` `To go on: /<skill> resume <your feedback>` `` and `Never call AskUserQuestion.` (lines 180-182).
- `docs/rule-anchors.md:53` has a row for it (hash `8c5d5c90`); rows 87 and 96 describe the review and fix `## Instructions`.
- Plans and change notes name it: `docs/plans/coder-worktree-fixes/plan.md:23`, `docs/plans/review-resume-asks/plan.md:10,64`, and `docs/changes/notes/*review-fork*` / `*asks-done*` / `*decide*` files (for example `docs/changes/notes/2026-11-07-review-and-fix-run-in-a-sonnet-fork-that.md:20`).

### 9. The rule-meter tool and where it stores data

Location: `~/agent-evals/bin/rule_meter.py` (the `~/agent-evals` repo, not this repo). Docstring (lines 1-39): "Rule-compliance meter: does a CLAUDE.md or agent-skill rule change what a headless session does?"

- One cell = a rule, a prompt level and an arm. `LEVELS = ("supportive", "neutral", "competing")` (line 86), `ARMS = ("on", "off")` (87), `DEFAULT_MODEL = "sonnet"` (85), `TIMEOUT_SECONDS = 1200` (88).
- A cell builds a bench tree from the ticketsim fixture, appends the global CLAUDE.md to the tree's project CLAUDE.md (arm off removes the rule's text), runs `claude -p` on the rule's task, and grades the recorded tool calls and tree with a detector. Outcomes: COMPLIED, VIOLATED, NO_TEST, NO_CHANGE, ERROR.
- Commands (docstring lines 22-31): `rule_meter.py run --rule A --level competing --arm on [--run 1] [--dry-run]`; `rule_meter.py run-all [--runs N] [--level L] [--dry-run]`; `rule_meter.py summary`. `~/agent-evals/CLAUDE.md` also names `run-all --rule <id>`.
- Scenarios: `~/agent-evals/bin/rule_meter_scenarios.json`, keyed by rule id (`"A"` is `no-unstage`, `"B"` is `changed-tests-only`, and so on), each with `name`, `rule_text`, `setup`, `detector`, `task`, and a `suffix` object per level. A scenario may name an `agent` and a `rule_source` (a toolkit file relative to `~/.claude`) and a `model` and a `plant`.
- Storage: `ROUND = ~/dev/evals/rulemeter1` (line 74 of the module block starting at 74-78: `BASE = ROUND / "base"`, `TREES = ROUND / "trees"`, `RUNS = ROUND / "runs"`, `RESULTS = RUNS / "results.jsonl"`). The docstring says "Run trees and outputs live under ~/dev/evals/rulemeter1/" (line 39). Run trees and streams are named `<rule>-<level>-<arm>-<run>` (for example `B-competing-on-3`). `run-all` runs only the runs `results.jsonl` lacks; ERROR runs are rerun.
- Related files in `~/agent-evals/bin/`: `rule_meter_config.py`, `rule_meter_fixture.py`, `rule_meter_plans.py`, `rule_meter_families.py`, `rule_meter_stacks.py`, `rule_meter_index.py`, `rule_meter_coder5.py`, `rule_meter_regress.py`, `rule_meter_shipped.json`, `rule_trials.py`, `rule_trials.jsonl`, `rule_trial_notes.json`, `rule_verdict.py`, `rule_sweep.py` and its `rule_sweep/*.json`, plants under `rule_meter_plants/` and `rule_stack_plants/` and `rule_sweep_plants/`, hidden checks under `rule_meter_checks/`, and tests `test_rule_meter*.py`.
- Policy that points to it: `~/agent-evals/CLAUDE.md` (the paragraph starting "No rule enters a toolkit skill, agent, command, hook prompt or CLAUDE.md ... without rule-meter runs", around lines 460-465): add the scenario to `bin/rule_meter_scenarios.json`, run both arms with `bin/rule_meter.py run-all --rule <id>`, put per-arm counts in the change file's Result; a rule the meter cannot grade is stated in `unmeasured`. It says to run `python3 bin/rule_trials.py search "<words>"` before writing a rule.
- Queue item that cites it for this skill: `~/agent-evals/queue/trim-the-code-skill-s-duplicated-prose-behind-rule.md` (title "Trim the /code skill's duplicated prose behind rule-meter runs", `components: ["skill/code"]`).
- In this repo: the toolkit's change notes carry `unmeasured:` fields where a rule had no meter run (for example `docs/changes/notes/2026-11-10-test-commands-named-in-a-review-resume-reply-run.md:15`); `docs/rule-anchors.md` rows list "rule meter" among evidence kinds (for example line 53).

### 10. Test patterns and fixtures under `tests/scripts/`

Runner and conventions: tests are `unittest` classes run through `python3 tests/parallel_tests.py <test file name>` and `bash tests/run.sh` (per `docs/toolkit-script-rules.md`). Path helper: `tests/scripts/toolkit_paths.py` (`TREE_CLAUDE_DIR` line 11, `CLAUDE_DIR` 12 honoring `TOOLKIT_CLAUDE_DIR`, `SCRIPTS_DIR` 13, `CODE_DIR` 14, `REVIEW_DIR` 15, `TELEMETRY_DIR` 16, `LIB_DIR` 17, `TOOLS_DIR` 18, `GATES_DIR` 19, `FIX_DIFF_SCRIPT` 20, `CODE_SKILL_FILE` 22, `CODE_FORK_AGENT_FILE` 23, `WORK_HOOKS` 27, `CODER_GATE_LIB_MODULES` 30; `first_python_that_starts` at 39). Its docstring says importing it guards the real ledger.

Files for the questioned surfaces:

- `tests/scripts/test_code_review_start.py` (625 lines), class `CodeReviewStartTest` (line 28). `REVIEW_START = toolkit_paths.CODE_DIR / "code_review_start.py"` (16); `PLAN` (17), `BASE = "abc1234"` (23), `SAMPLE_COMMANDS`, `STALE_PROSE_COMMAND`. Helpers: `setUp` (29), `start(*extra, env=None)` (38, runs the script as a subprocess), `load_module` (86, imports the script as a module for mocks), `run_live` (119), `git` (246), `commit_base` (355), `commit_empty` (504), `run_main` (508), `held_rows(unchanged, live_row, phase="2")` (430). Held and scope cases:
  - `held_rows` patches `phase_start.unchanged_dirty_files`, `session_registry.other_live_session_in` and `CLAUDE_CODE_SESSION_ID`, then calls `phase_held_files`.
  - `test_a_dirty_file_is_held_only_when_another_live_session_works_in_the_repo` (438); `test_a_holder_with_no_name_is_recorded_by_its_session_id` (448); `test_a_file_an_earlier_phase_of_the_plan_names_is_never_held` (453); `test_a_file_a_numbered_step_of_an_earlier_phase_names_is_never_held` (460); `test_the_run_session_id_is_passed_so_it_is_never_its_own_holder` (469, `assert_called_once_with(self.repo, "test-session")`); `test_an_unset_session_id_holds_nothing_and_does_not_exit` (479); `test_a_dry_run_with_no_session_id_prints_the_prompt` (492); `..._says_in_its_output_that_no_file_is_held` (520); `test_a_holder_with_no_name_and_no_session_id_is_recorded_by_its_pid` (581); `test_the_prompt_carries_a_held_by_line_with_the_holder_rows` (586).
  - Scope: `test_a_merge_commit_after_the_phase_is_left_out_of_the_review_diff` (251); `test_a_merge_that_cannot_fold_into_the_base_stops_the_run_naming_it` (282); `test_the_handoff_files_come_from_git_and_only_the_coders_why_lines_are_kept` (362); `test_the_handoff_files_leave_out_the_plan_folder` (386); `test_a_base_that_is_not_a_commit_stops_the_run_when_the_handoff_lists_files` (422); `test_a_detached_run_hands_its_review_scope_to_the_child_which_does_not_compute_it_again` (531); `test_a_later_phase_file_this_phase_already_changed_is_not_a_later_phase_file` (73).
  - Handoff phases and detach: lines 170-200 (`handoff-phases.json` cases), 200-232 (`detach` cases), 408-420 (unreadable phases file), 603 (wait command and pid file).
- `tests/scripts/test_phase_start.py` (443 lines), class `PhaseStartTest` (23). `PHASE_START` takes env `PHASE_START_SCRIPT` or `toolkit_paths.CODE_DIR / "phase_start.py"` (13); `REVIEW_START` is its sibling (14); `ENV` sets `CLAUDE_CODE_SESSION_ID: test-session` (15); `git(repo, *args)` (18). Helpers: `setUp` (24), `phase_start` (42), `phase_start_with(*flags)` (45), `recorded_dirty` (49), `review_prompt(base)` (188, runs the real `code_review_start.py --dry-run`), `register_live_session(session_id, cwd)` (193, writes `<config_dir>/sessions/<id>.json` with `{"pid": os.getpid(), "sessionId", "name": "lane-b", "cwd"}`), `unrelated_commit` (243), `other_repo_with_recorded_stop` (301), `resume_in_repo` (313). File-state cases:
  - `test_the_record_names_head_and_every_dirty_file_and_the_sha_is_printed` (198): writes `theirs.py` (modified) and `new.txt` (untracked), then reads `.git/code-phase/start.json` and asserts `record["dirty"]` keys.
  - `test_a_file_dirty_at_the_phase_start_with_the_same_bytes_is_held_out_of_the_review` (211): `theirs.py` and `shared.py` dirty at start, `mine.py` added and `shared.py` rewritten after, one live other session; asserts the `held files:` and `held-by:` header lines and that `shared.py` and `mine.py` stay in the handoff.
  - `test_a_dirty_file_with_no_other_live_session_in_the_repo_is_the_runs_own_and_is_reviewed` (231): only the run's own session and one in `self.repo.parent` are live.
  - `test_no_record_holds_no_file_and_says_so` (432).
  - Record handling: 78 (same head keeps the record), 89 (`--new-run` replaces), 99 (moved head replaces), 110 (a record that does not parse is replaced with a named note), 122 (unknown argument), 251/261/270/279/290 (base versus recorded head: unrelated, ancestor, resume base, descendant that is not HEAD, committed-phase resume).
  - Move-aside: 129 (`stop.md` to `stop.prev.md`), 143 (`handoff.txt` to `handoff.prev.txt`), 155, 164, 176 (failed renames).
  - Resume refusals: 317-415 (the session's recorded stop in another run folder).
  - `test_a_review_start_that_exits_early_leaves_no_earlier_phase_packet_for_the_wait` (52).
- Review-loop tests (hold logic inside the loop): `tests/scripts/test_review_loop_script.py` (about 5000+ lines; 158 lines match "held"). Held cases include 162 (a held item recorded once), 178 (no holder row stays with the coder), 203 (match only by file itself or tail), 217 (tail names one held file and no owned file), 231 (exact path to an owned root file beside a held nested file of the same name), 251/258/263 (implicit holders: live other session, none, no `--file` scoping), 271 (held file deleted during the call is named), 1177-1285 (held files kept out of the review and fix; changes during a coder call, also a failed coder call; absolute path; no holder row; held beside a real one), 1304-1417 (plan-routed decision, plan ask, tail path shared with an owned file, design ask, given finding), 1493-1525 (held class members), 1690-1708 (held nits), 1843-1858 (held untracked file the coder deletes is put back), 2690 and 2736 (prompt size and directory folding with held files), 4949-4985 (held finding re-reported then fixed). Related: `tests/scripts/test_review_loop_coder.py:172`, `test_review_loop_prompt_file.py` (7 held matches), `test_review_loop_closure.py` (6), `test_review_loop_ruled.py` (25), `test_handback.py` (35).
- Other review-loop test files: `test_review_loop_round_two_fixes.py`, `test_review_loop_named_tests.py`, `test_review_loop_findings.py`, `test_review_loop_closure.py`, `test_review_loop_coder.py`, `test_review_loop_prompt_file.py`, `test_review_loop_ruled.py`, `test_review_loop_script.py`.
- Lib tests touching the same modules: `test_worktree_snapshot.py`, `test_session_registry.py`, `test_merge_free_base.py`, `test_reviewed_tree.py`, `test_reviewed_tree_shared_record.py`.
- Run-folder and gate tests: `test_code_wait.py`, `test_code_relay.py`, `test_coder_gate.py`, `test_fork_write_scope.py` (`FORK_AGENT = toolkit_paths.CLAUDE_DIR / "agents" / "code-fork.md"`, line 15; `run_hook(file_path, agent_type="code-fork")`, 18), `test_open_child_gate.py` (`agent_type="code-fork"`, line 95), `test_import_guard.py` (`CODE_FORK_PAYLOAD`, line 19; `FORK_WRITE_SCOPE`, 21), `test_review_launch.py`, `test_log_review_finding.py` (`CODE_SKILL = ... "skills/code/SKILL.md"`, line 24; used at 340).
- Guidance-text pin tests: `tests/scripts/test_code_skill_text.py` (`test_no_git_command_for_the_user`, line 15, over `CODE_SKILL_FILE` and `CODE_FORK_AGENT_FILE`; `test_stop_blocks_name_the_commit_subject`, line 24) and `tests/scripts/test_guidance_rules.py`: code-fork feedback sentence (line 29-32), SKILL.md stop and ask pins (34-45), review and fix `context: fork agent: code-fork model: sonnet` plus `code_relay.py` and `launch --detach` (173-177), review-fork-run pins (179-182), cancel pins for SKILL.md and code-fork.md (185-192), done-clause criterion pin (194-199). These read text through `guidance_text(<path under TK>)`.

How tests pin file-state cases (from the code read above): each builds a real temp git repo, writes files in the states under test (modified tracked, untracked, rewritten after the start record), runs `phase_start.py` or `code_review_start.py` as a subprocess or loads it as a module and patches `phase_start.unchanged_dirty_files` and `session_registry.other_live_session_in`, and asserts on the printed header lines (`held files:`, `held-by:`), the handoff `- path:` entries, or `.git/code-phase/start.json`. Live sessions are faked as registry JSON rows with `pid = os.getpid()` in a temp config dir.

### 11. Other consumers of /code sections, code-fork text, and ported opencode copies

Skills and shared docs that name `/code` or its parts (from `rg`):

- `TK/skills/verify-branch/SKILL.md:3,9,11,74`: runs after `/code`; "`/code`'s `## Phase Status` checkboxes are self-reported"; "`/code`'s Verify pass".
- `TK/skills/triage/SKILL.md:46-48,59,68`: routes XS to `/code +fast`, S to `/code`, M to `/code` (`+deep`).
- `TK/skills/eng-spec/phases/7-handoff.md:5,14`: prints `/code docs/plans/<slug>/spec.md`; `eng-spec/phases/6-finalize.md:46` and `7-handoff.md:7` run `plan_check.py`; `eng-spec/templates/spec-template.md:4,28`; `eng-spec/SKILL.md:3`.
- `TK/skills/_shared/closing-phases.md:3`, `plan-format.md:3,16,17,25,61`, `plan-reading.md:5` ("Consumers: `/code` (step 2 orchestrator read, step 3 coder dispatch)"), `handoff-block.md:3,26,28` ("Producers `/code` + `/fix`"), `code-vocabulary.md:5` (consumers list), `review-fork-run.md` (question 8).
- `TK/skills/review/log-review-finding:31` mentions "gate ran at a /code phase boundary".
- `TK/skills/close-branch/SKILL.md:23` (`concentration.py`), `TK/skills/refactor/scripts/refactor_flow.py:327`, `TK/skills/todos/SKILL.md:37`, `TK/skills/audit/review.md:7` (`/code` prohibition scans via `log-scan`), `TK/skills/drive/SKILL.md:3`.
- Agents: `TK/agents/coder.md:3` ("Dispatched by /code, /refactor, /deps and the review loop"); `TK/agents/spec-criteria.md:56,58`; `TK/agents/smell-reviewer.md:19` reads a heading of `code-reviewer.md`.
- Global rules: `TK/orchestration.md:5,36` ("dispatch via `/code`"; `herdr-phase-change` from /eng-spec to /code); `TK/CLAUDE.md:26`; `TK/README.md:63-121`.
- Hooks and scripts that name code-fork text or the run folder: `settings.json:478-482` (`fork_write_scope.py`), `settings.json:442-457` (`open_child_gate.py`, `handback.py hook handback`, `coder_gate.py hook`), `TK/scripts/lib/script_utils.py:33`, `TK/scripts/lib/stop_file_names.py:2`, `TK/scripts/lib/review_fix_names.py:2`, `TK/scripts/CLAUDE.md:28` (owner line for stop file names).
- Telemetry rows tied to `/code`: `TK/skills/audit/review.md:7` (`scan_run` rows via `log-scan`); SKILL.md calls `log-scan scan=acceptance-stub` (line 51) and `scan=prohibition` (line 60).
- Docs: `docs/glossary.md:87` (handoff), `:221` (`coder_packet.py`), `:271-275` (`code-fork`), `:283` (handoff block), `:295-297` (run folder), `:301-303` (stop file); `docs/rule-anchors.md` rows 53, 83, 85, 87, 94, 96 (sections of `skills/code/SKILL.md`, review and fix SKILL.md, `review-fork-run.md` with hashes); `docs/changes/changelog.md` and `docs/changes/notes/*` (many rows with components `skill/code`, `agent/code-fork`, `shared/review-fork-run`); `docs/changes/what-worked.md:20`; `docs/changes/ruled-out.md:125`; `docs/changes/fixes-by-script.md:93` (`agent/code-fork`); plans `docs/plans/fix-gates-and-fork-1107/plan.md:10,58,65`, `docs/plans/code-wait-handoff-close-branch/plan.md:5,114`, `docs/plans/review-resume-asks/plan.md:10,35-47,64`, `docs/plans/verify-misc-batch/plan.md:15`.
- Tests pinning text: question 10, last bullet.

Ported opencode copies (`opencode/.config/opencode/`):

- `commands/code.md` (4 lines): frontmatter `description: Dispatch coder subagent(s) for implementation, then auto-run review - auto-detects scope or accepts be/fe/fs modifier`; body `Load the `code` skill and follow its instructions. $ARGUMENTS`. It carries no step text.
- `agents/coder.md`: ported; line 3 repeats the dispatcher list; line 9 reads `~/.claude/skills/coder-core/SKILL.md` and substitutes `CLAUDE.md` to `AGENTS.md`.
- `agents/` also holds `code-reviewer.md`, `smell-reviewer.md`, `complexity-reviewer.md`, `test-reviewer.md`, `test-intent-reviewer.md`, `plan-reviewer.md`, `spec-criteria.md`, and others; there is no `code-fork.md` and no `review-fork-run` under `opencode/`.
- `commands/triage.md:2` repeats the route to `/code`; `commands/review.md`, `commands/fix.md`, `commands/eng-spec.md` exist.
- `agents/code-reviewer.md:57` and `agents/spec-criteria.md:52` repeat text that names planning-pipeline vocabulary and `_shared/code-vocabulary.md`.
- A plan line (`docs/plans/fix-gates-and-fork-1107/plan.md:65`) says "patch the opencode port of code-fork if" one exists; no such file is present in `opencode/.config/opencode/agents/`.
- Root `CLAUDE.md` rule that governs this: the toolkit-edit propagation sweep (consumers, then the ported copy in `opencode/.config/opencode/agents/`, then inheriting variants).

### Dormant scaffolding on the questioned surfaces

Checked with `rg -w` over `claude` and `tests` (hidden dirs included):

- `PREVIOUS_HANDOFF_FILE` and `PREVIOUS_LOOP_DIR_FILE` (`code_wait.py:72,77`) are read only by `phase_start.py:168-169`; nothing reads a `handoff.prev.txt` or `loop-dir.prev` file after it is written.
- `PREVIOUS_STOP_FILE` is read by `code_relay.py:58` and `phase_start.py:139`; `relayed` and `bounced` files are read and written inside `code_relay.py`.
- `NOTES_PATHS_FILE` (`notes_paths.py:13`) is used only on `notes_paths.py:14` (`COMMITTED_LIST`).
- `worktree_snapshot.staged_paths` (`worktree_snapshot.py:52`) has no caller outside `worktree_snapshot.py` in `claude`; `tests/scripts/test_stage_run.py` defines its own method of that name, unrelated.
- `reviewed_tree.record_shared_base` (308) is called once, at `reviewed_tree.py:305`; `last_commit_fingerprint` (423) once, at `reviewed_tree.py:417`.
- `session_registry.session_display_name` (76) has one production caller (`review_loop_main.py:229`) and test callers in `test_session_registry.py`.
- `code_wait.py` functions with one reference beyond the definition, all inside that file: `phase_review_output` (286), `stale_loop_line` (464), `print_ended_loop` (530).
- `HELD_FAULTS` (`review_loop_held.py:15`) is a module-level list filled by `note_changed` and read by `review_loop_coder.py:22`; it is never reset in `review_loop_held.py`.
- `code-fork.md` `disallowedTools` names `Edit, NotebookEdit` only (`code-fork.md:5`); `Write` is permitted and held by the `fork_write_scope.py` hook.
- `TK/skills/review/SKILL.md` and `TK/skills/fix/SKILL.md` `allowed-tools` omit `Skill`; `/code` includes it (`SKILL.md:7`).
- No enum values never assigned were found in the questioned modules.

## Code References

- `TK/skills/code/SKILL.md:1-8` - frontmatter (`context: fork`, `agent: code-fork`, `model: sonnet`, `allowed-tools`).
- `TK/skills/code/SKILL.md:36-98` - steps 0-6.
- `TK/skills/code/SKILL.md:100-157` - Phase-Complete Block B and C.
- `TK/agents/code-fork.md:1-15` - fork agent definition.
- `TK/agents/coder.md:1-12` - coder agent definition.
- `TK/skills/_shared/review-fork-run.md:1-19` - shared review and fix fork steps.
- `TK/skills/review/SKILL.md:14`, `TK/skills/fix/SKILL.md:14` - references to the shared file.
- `TK/scripts/code/phase_start.py:38-39,46-56,83-100,150-196` - start record and phase start.
- `TK/scripts/code/code_review_start.py:73` - `HANDOFF_PHASES_FILE`.
- `TK/scripts/code/code_review_start.py:101-176` - handoff files from git, changed files, held files.
- `TK/scripts/code/code_review_start.py:180-233` - `ReviewScope`, `read_scope`, `diff_base`, `review_scope`.
- `TK/scripts/code/code_review_start.py:285-444` - `detach`, handoff phase records, `run_scope`, `main`.
- `TK/scripts/code/code_wait.py:52-79,164-220,399-580` - run folder constants, phase run record, waits.
- `TK/scripts/code/code_relay.py:38-52,146-191` - relay constants and `relay`.
- `TK/scripts/code/coder_gate.py:94-143,180-235,258-290,784-830` - gate constants, files, set, hooks.
- `TK/scripts/code/coder_packet.py:21-28,147-179` - packet usage, gate evidence.
- `TK/scripts/review/review_loop_held.py:15-141` - hold logic.
- `TK/scripts/review/review_loop_main.py:150-153` - hold wiring.
- `TK/scripts/review/review_loop_script.py:390,487-502,843` - held items in the loop and the packet.
- `TK/scripts/review/handback_store.py:23-52,55-80,307-317` - store constants, paths, `record`.
- `TK/scripts/review/handback_hook.py:219-247` - dispatch and step rows.
- `TK/scripts/gates/fork_write_scope.py:25,54-117` - code-fork Write gate.
- `TK/scripts/lib/session_registry.py:37-76` - live sessions and holder label.
- `TK/scripts/lib/worktree_snapshot.py:24-141` - snapshot and hashes.
- `TK/scripts/lib/merge_free_base.py:84` - merge-free base.
- `TK/scripts/lib/reviewed_tree.py:84,214,251,358` - fingerprints.
- `TK/scripts/lib/notes_paths.py:11-78` - notes paths.
- `TK/scripts/lib/stop_file_names.py:4-9`, `TK/scripts/lib/code_stop_record.py:9-31` - stop names and record.
- `TK/settings.json:225,254,352,442-457,478-482,565,575,594,617` - hook wiring.
- `tests/scripts/test_code_review_start.py:28,430-600` - review start and held-row tests.
- `tests/scripts/test_phase_start.py:23,193-240` - phase start and held-file tests.
- `tests/scripts/test_review_loop_script.py:162-271,1177-1525,1690-1858,4949-4985` - held-item tests in the loop.
- `tests/scripts/toolkit_paths.py:11-36` - path helpers.
- `tests/scripts/test_guidance_rules.py:29-45,173-199` and `tests/scripts/test_code_skill_text.py:15-25` - text pins.
- `~/agent-evals/bin/rule_meter.py:74-88` - rule-meter storage and constants.
- `~/agent-evals/bin/rule_meter_scenarios.json` - scenarios.

## Patterns Found

- Every fork run keeps state in `<git dir>/code-phase` (named by `git rev-parse --path-format=absolute --git-path code-phase`), with file-name constants split between `code_wait.py`, `stop_file_names.py` and `code_review_start.py`.
- The fork writes only run-folder files, by Write tool, and a PreToolUse hook (`fork_write_scope.py`) enforces it for agent type `code-fork`.
- The fork hands back through a stop file; the main session reads it through `code_relay.py`; a session stop record (`code_stop_record.py`) lets `phase_start.py --resume` refuse a resume in the wrong run folder.
- Long steps run detached (`--detach`, `start_new_session=True`) and the fork polls with `code_wait.py`, which prints `Still working. Run the same command again.` (`code_wait.py:57`).
- Steps pass state as JSON files (`start.json`, `review-scope.json`, `run.json`, `handoff-phases.json`, `coder-gate.json`) written with `script_utils.write_text_atomically`.
- A gate script reads the event's `agent_type` and returns at once for other agents (`coder_gate.py:787`, `fork_write_scope.py`).
- Hold logic splits in two: start time (`phase_start.py` records dirty hashes; `code_review_start.py` turns same-bytes files plus a live other session into holder rows) and loop time (`review_loop_held.py` skips findings on held files and notes held-file changes).
- Tests build real temp git repos, run scripts as subprocesses or load them as modules and patch collaborators, and fake live sessions with registry JSON rows.
- Guidance text is pinned by substring assertions on skill and agent files (`guidance_text`).
- Skill text for /review and /fix is shared through one file the fork reads first (`review-fork-run.md`), while /code holds its own steps inline.
- Rule changes to toolkit text are recorded in `docs/changes/notes/*` with `unmeasured:` fields and in `docs/rule-anchors.md` by section hash.

## Reuse Inventory

Run-folder and waits (`TK/scripts/code/code_wait.py`):

- `phase_dir(repo) -> Path` - `code_wait.py:169` - the `<git dir>/code-phase` folder.
- `phase_dir_or_none(repo) -> Path | None` - `:164`.
- `running_review_pid(repo) -> int | None` - `:176` - pid of a running review loop.
- `loop_dir(repo)` - `:186` - the running loop's folder.
- `write_phase_run(repo, lane, phase, loop_folder=None)` / `read_phase_run(repo)` - `:195` / `:206` - `run.json`.
- `checked_agent_id(word)` - `:158` - validates `a` + 16 hex.
- `wait_agent(agent_id)` - `:399`; `wait_review(repo, words=(), launched_folder=None)` - `:476`.
- `plan_impact_notice(repo)` / `phase_asks_notice(repo)` - `:222` / `:243`.

Phase start (`phase_start.py`):

- `start_record(repo) -> {"head","dirty"}` - `:46`.
- `read_start_record(repo)` - `:58`.
- `unchanged_dirty_files(repo, base_commit) -> list | None` - `:83`.
- `base_relates_to_head(repo, base_commit, head)` - `:73`.
- `move_aside(folder, name, previous_name)` - `:103`.
- `resume_base(repo, kept)` - `:118`.
- `other_run_refusal(run_folder)` - `:130`.

Review start (`code_review_start.py`):

- `review_scope(repo, base, coder_handoff, plan=NO_PLAN, phase="") -> ReviewScope` - `:217`.
- `phase_held_files(repo, base_commit, plan=NO_PLAN, phase="", notes=None)` - `:148`.
- `handoff_with_git_files(repo, base_commit, handoff, held=(), plan=NO_PLAN)` - `:101`.
- `phase_changed_files(repo, base_commit, held=())` - `:128`.
- `earlier_phase_files(repo, plan, phase)` - `:133`.
- `diff_base(repo, base_commit)` - `:205`.
- `read_scope(scope_file)` - `:196`.
- `coder_why_blocks(entry_lines)` - `:83`.
- `held_note(notes, message)` - `:141`.
- `record_handoff_phase(repo, plan, phase, handoff_text)` / `read_handoff_phases(phases_file)` - `:332` / `:312`.
- `phase_gate_commands(repo, plan, phase, base, handoff="")` - `:265`.
- `review_prompt(repo, lane, plan, phase, handoff, phase_changed=(), holders=(), review_base=None, coder_model="")` - `:236`.
- `detach(repo, argv, scope)` - `:285`.

Hold logic (`TK/scripts/review/review_loop_held.py`):

- `run_held_files(repo, caller_held, only_files)` - `:18`.
- `implicit_holders(repo, held_files, known_holders, only_files, own_session_id)` - `:28`.
- `held_path_in_repo(path, repo)` - `:45`.
- `names_held_file(path, held_path)` - `:55`.
- `tail_names_held_file(path, held, owned)` - `:63`.
- `held_path_of(item, held, owned, repo)` - `:70`.
- `split_held_findings(items, held, owned, repo)` - `:83`.
- `caller_holders(caller_held, held_by)` - `:95`.
- `held_reason(holder)` - `:104`.
- `skip_held_items(items, held, owned, held_unfixed, repo, holders)` - `:108`.
- `digests(repo, held)` - `:128`.
- `note_changed(role, repo, before)` - `:134`.
- `holder_row(path, session, claim)` - imported from `review_loop_prompt_file` (`review_loop_held.py:12`).

Sessions and snapshots (`TK/scripts/lib/`):

- `session_registry.other_live_session_in(folder, own_session_id)` - `:54`; `live_session_rows()` - `:37`; `holder_label(row)` - `:69`; `session_display_name(session_id)` - `:76`; `sessions_dir()` - `:21`; `projects_dir()` - `:29`; `config_dir_override()` - `:13`.
- `worktree_snapshot.status_entries(root)` `:24`; `status_codes(root)` `:47`; `staged_paths(root)` `:52`; `file_hash(root, path)` `:57`; `working_tree_changes(root)` `:69`; `work_tree_tree(repo)` `:111`; `take(repo)` `:129`; `changes_since(before)` `:141`.
- `merge_free_base.merge_free_base(repo, base)` `:84`; `merge_commits(repo, base)` `:33`.
- `reviewed_tree.tree_fingerprint(...)` `:84`; `work_tree_fingerprint(repo, log=None)` `:214`; `fingerprint(repo_dir)` `:236`; `reviewed_fingerprint(repo_dir, base="HEAD")` `:251`; `record_reviewed(session, repo_dir, tree=None)` `:358`; `is_reviewed(session, repo_dir, tree=None)` `:380`; `push_review_state(repo_dir)` `:318`; `shared_record_covers(repo_dir)` `:404`.
- `notes_paths.committed_notes_list(top, timeout=None)` `:50`; `is_notes_path(path, declared_paths)` `:69`; `exclude_pathspecs(declared_paths)` `:78`; `notes_list_errors(text, name)` `:40`.
- `code_stop_record.record_stop(session, run_folder, repo_top, go_on)` `:24`; `last_stop(session)` `:31`; `stop_record_dir()` `:15`; `stop_record_path(session)` `:20`.
- `stop_file_names`: `STOP_FILE`, `REVIEW_STOP_FILE`, `STOP_FILES`, `PREVIOUS_STOP_FILE` - `:4-9`.
- `script_utils`: `changed_files(directory, base="HEAD", with_deleted=False)` `:491`; `without_paths(files, paths)` `:946`; `git_output(cwd, *args, timeout=None)` `:297`; `git_path(cwd, name)` `:503`; `head_commit(cwd, timeout=None)` `:441`; `is_ancestor(repo, older, newer, timeout=None)` `:436`; `repo_root(cwd, timeout=None)` `:574`; `write_text_atomically(path, content)` `:1239`; `state_file_path(state_dir, name, suffix)` `:1279`; `read_jsonl(path)` `:1323`; `sortable_unique_id(now=None)` `:1097`; `read_ledger(args, wait_seconds=LEDGER_WAIT_SECONDS)` `:728`; `text_similarity(first, second)` `:208`.

Coder gate and packet:

- `coder_gate.gate_path(cwd)` `:180`; `set_gate(commands, gate_assignments=())` `:258`; `clear_gate()` `:316`; `print_gate_summary()` `:299`; `write_session_pointer(session_id, gate_file)` `:193`; `read_session_pointer(session_id)` `:200`; `remove_session_pointer(session_id, gate_file)` `:214`; `hook_gate_file(event)` `:225`; `run_hook()` `:784`; `run_bash_hook()` `:815`; `whole_package_reason(command, cwd)` `:245`.
- `coder_packet`: `phase_bounds(plan_lines, phase_number)` `:28`; `cited_sections` `:39`; `gate_evidence_refusal` `:147`; `gate_evidence_text` `:160`; `bullet_list` `:179`.
- `coder_report`: `open_questions(report)` `:17`; `plan_impact_block(report)` `:56`; `has_plan_impact_block(report)` `:70`; `recommends_eng_spec(report)` `:79`; `why_by_file(report)` `:84`; `skipped_issues(report, issue_count)` `:101`; `behavior_lines(report)` `:142`.

Handback store (`TK/scripts/review/handback_store.py`):

- `store_dir()` `:55`; `session_file(session_id)` `:60`; `session_rows(session_id, kind=None, agent_id=ANY_AGENT)` `:71`; `record(session_id, kind, **fields)` `:307`; `record_handback(session_id, **fields)` `:317`; `latest(session_id)` `:335`; `latest_for_repo(session_id, repo_top)` `:367`; `hand_back_standing(session_id)` `:348`; `hand_back_gap(seen)` `:437`; `record_ruled_impact(...)` `:96`; `rulings(session_id, repo)` `:189`; `record_rejected_ask(session_id, text, repo)` `:211`; `rejected_ask_texts(session_id, repo)` `:237`; `phase_asks_state(repo)` `:670`; `unruled_phase_asks(repo)` `:683`; `ruled_rows_repo(path)` `:79`.
- `handback_hook.record_script_dispatch(session_id, repo_dir, no_review=False)` `:241`.

Relay (`code_relay.py`): `newest_stop(folder)` `:55`; `go_on_line(text)` `:64`; `with_resume_path(text, repo_top)` `:72`; `edited_after_clean_review(repo)` `:92`; `relay(repo)` `:146`.

Write gate (`fork_write_scope.py`): `in_run_folder(file_path)` `:54`; `pending_launch_reason(file_path)` `:67`; `review_fix_route_reason(file_path)` `:92`; `write_deny_reason(payload, hook_input)` `:104`.

Test helpers (`tests/scripts/`):

- `toolkit_paths` constants and `first_python_that_starts(names)` - `toolkit_paths.py:11-39`.
- `PhaseStartTest.register_live_session(session_id, cwd)` - `test_phase_start.py:193`; `phase_start()` `:42`; `phase_start_with(*flags)` `:45`; `recorded_dirty()` `:49`; `review_prompt(base)` `:188`; `unrelated_commit()` `:243`.
- `CodeReviewStartTest.held_rows(unchanged, live_row, phase="2")` - `test_code_review_start.py:430`; `load_module()` `:86`; `start(*extra, env=None)` `:38`; `run_live(...)` `:119`; `run_main(...)` `:508`; `commit_base()` `:355`; `commit_empty()` `:504`.
- `test_phase_start.git(repo, *args)` - `test_phase_start.py:18`; `PLAN` and `BASE` constants - `test_code_review_start.py:17,23`.
- `guidance_text(<path under TK>)` - used in `test_guidance_rules.py`.
- `run_hook(file_path, agent_type="code-fork")` - `test_fork_write_scope.py:18`.

Rule-meter (`~/agent-evals/bin/`):

- `rule_meter.py run | run-all | summary`; `rule_meter_scenarios.json`; `rule_meter_shipped.json`; `rule_trials.py search "<words>"`; `rule_meter_regress.py`; results at `~/dev/evals/rulemeter1/runs/results.jsonl`.
