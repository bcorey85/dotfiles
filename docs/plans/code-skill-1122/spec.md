# Code skill fixes, November 2026: fork children on cancel, held dirty paths, /code trim

> Ticket: ./00-ticket.md (three queue items plus the folded rank-1011 item `code-skill-dedupe-the-stop-rule-and-move-the-phase`)
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-22

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

Three defects in the /code skill, one branch. A TaskStop on a /code fork leaves its coder running: a new `scripts/code/fork_children.py` names the fork's live children (CLI verb) and denies the TaskStop once while children live (hook verb). A /code phase review drops its hold on a file another session owned once that session edits it again: when another session is live at a phase start it is recorded as the holder, every path recorded dirty at the run start then stays held for the whole phase, a changed held file is named as a tool fault, and under a holder an untracked file no recorded coder of the run wrote is held too. The text /code loads at start is 3828 words across four files: the Phase-Complete section moves to a sibling file read at phase end, each stop rule gets one owner, dense paragraphs become lists, and the in-load duplicates are cut behind rule-meter runs.

## Phase Status

<!-- Hoisted from below so the first screen answers "where are the agents?". The one section that changes after writing (/code ticks it) — source of truth for "which phase is next". Do not move it back down. -->

- [x] Phase 1: fork_children.py, the interrupted reading and the cancel route (risk: low)
- [x] Phase 2: hold every start-dirty path, name changed held files, hold foreign untracked files (risk: low)
- [x] Phase 3: /code trim, phase-end file, stop-rule owners, anchors, meter runs (risk: low)
- [ ] Phase 4: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

Single-stream plan: the three phases share no new contract, so Phase 0 is folded into each phase's `**File**` list and the Data shapes in `## Approach`.

## Decisions

<!-- One line per block in 03-decisions.md's ## Resolved. -->

1. Item 1 mechanism — `scripts/code/fork_children.py` with a `<fork id>` CLI verb (prints live child ids, stops the run's detached review loop) and a `hook` verb (PreToolUse TaskStop deny, once per fork, naming the ids); liveness from `open_child_gate.live_children` plus a `parentAgentId` meta scan plus a new `agent_interrupted` reading in `lib/loop_transcript.py`. Trade-off: the deny does not fire until the settings.json line lands; the cancel route in SKILL.md names the command.
2. Item 2 hold signal — each phase start records a holder in start.json (the other live session in the repo at that moment; kept once set). When start.json names a holder, every path in its `dirty` map is held for the whole phase, whether or not that session is still live at review; with no recorded holder the run behaves as today. `unchanged_dirty_files` becomes `recorded_dirty_files`. A held file whose bytes differ from the record is a tool fault, written into the review prompt. Trade-off: the run's own edit of a start-dirty file goes unreviewed and is named as a tool fault in the prompt.
3. Item 2 untracked attribution — start.json records every session id that ran the phase (a resume adds its id). Under a holder (the recorded one, or else another session live at review), an untracked file is held and named when it is not in start.json `dirty`, is outside the plan folder, and no recorded session's subagent coder wrote it (Write/Edit/NotebookEdit paths in their transcripts). Trade-offs: a file a coder-run generator wrote is held, not reviewed; a file the review loop's `claude -p` fix coder made in an earlier round is held, with the note, until the review lane records its coder's writes (queue item `review-loop-s-fix-coder-writes-are-not`).
4. Item 3 cut set — cut the in-load duplicates (6 + 8 words), meter and cut SKILL.md's restatement of global CLAUDE.md's Ticket AC rule, fold rank 1011: one owner per stop rule, dense paragraphs to lists, the Phase-Complete section to `skills/code/phase-end-block.md`, anchor rows updated. Trade-off: one more Read per phase end.
5. Nature of the 2026-11-22 cancel — a mechanism gap on the direct-TaskStop route; the change file is worded on it.
6. Architect design gaps — ruled by agent-evals-c3, 2026-11-22: rule-meter scenarios go in `~/agent-evals/bin/rule_meter_scenarios.json` (committed alone); item 1's first AC is pending the settings.json wiring, not met; rank-1011 bullet 4 is split to queue item `dedupe-the-acceptance-criteria-none-rule-across`; `code_wait.py` prints the held-changed tool-fault line; the whole Phase-Complete section moves; the hook fixture is built from a transcript TaskStop input until a captured event exists. Untracked folders need no expansion: `status_codes` already runs `--untracked-files=all` (the plan-review fact check of 2026-11-22 dropped the expansion ruling, which rested on a wrong reading).
7. Plan review round 1 (ledger block 9) — the holder recorded at phase start holds for the whole phase; start.json records every session that ran the phase and attribution reads all of them; AC2 (a replay of a cancel during the coder step writes nothing after the stop) is manual-only via AC20; the AC15 count runs on the four-file start load (limit 3445; the limit became 3488 in block 12). With no recorded holder, "unchanged" means today's rule: same-bytes start-dirty files held only while another session is live at review.

## Approaches Considered and Not Taken

The architect named three whole-feature approaches and ruled each out:

- Record children at dispatch inside `code_wait.py agent` and read the list at stop: a second liveness owner beside `lib/loop_transcript.py`, misses an agent dispatched without a wait, goes stale on cancel.
- Deny the coder's Bash through `coder_gate.py` once the fork is gone: stops Bash only, and the incident's write was a Write tool call.
- Attribute untracked files through the handoff block's WHY/`files:` paths: `WHY: none` is allowed, so a real coder file would vanish from review.

## Constraints

- Out of bounds on this branch (other live lanes own them): `claude/.claude/scripts/review/*` (including `claude/.claude/scripts/review/verify-prep`), `claude/.claude/scripts/gates/*`, `claude/.claude/scripts/code/plan_check.py`, `claude/.claude/settings.json`, every `CLAUDE.md`, every `orchestration.md`. Importing from `review/` is allowed; editing is not. `tests/scripts/branch_bounds.py` (Phase 4) enforces this list. `exercised`: lane brief and `03-decisions.md` Direction.
- Owners (`claude/.claude/scripts/CLAUDE.md`): agent liveness `lib/loop_transcript.py` (`agent_finished`, `finished_by_meta`); child enumeration `review/open_child_gate.py` `live_children`; pid alive `lib/process_group.py`; session folders `lib/session_registry.py`; file hashes `lib/worktree_snapshot.py file_hash`; atomic writes `lib/script_utils.py write_text_atomically`; once-per-agent memory `review/handback_store.py` `record`/`was_recorded`. No second copy of any. `declared-only`.
- `script_utils.py` is 1378 lines; no new verb or reader goes in it (toolkit-script-rules Size). New readers go in `lib/loop_transcript.py` (525 lines). `exercised`: `wc -l`.
- `worktree_snapshot.status_codes` runs `git status --porcelain -z --find-renames --untracked-files=all` (lib/worktree_snapshot.py:27-28). Every untracked file is its own entry, so no folder expansion code is written. `exercised`: plan-review fact check, 2026-11-22.
- Toolkit scripts run on Python 3.10; `sys.path` lines from `Path(__file__).resolve()`; tests under `tests/scripts/` run through `python3 tests/parallel_tests.py <file>`; lint through `bash tests/lint.sh <py files>`. `declared-only`: `docs/toolkit-script-rules.md`.
- Hook contract (`omp` bridge): hook JSON on stdin, `permissionDecision` JSON or exit 2 out. `fork_children.py hook` denies through `script_utils.pre_tool_use_deny` and is fail-open with a comment saying so. `declared-only`: repo CLAUDE.md omp section.
- Skill and agent bodies carry rules, never rationale (repo CLAUDE.md). Every reworded sentence in `SKILL.md`, `code-fork.md` or `handoff-block.md` gets rule-meter on/off runs; a byte-for-byte move does not. `declared-only`: ruling 4.
- Text pins to keep green or retarget: `tests/scripts/test_guidance_rules.py` (:29-56, :84-92, :184-211), `tests/scripts/test_code_skill_text.py`, `tests/scripts/test_rule_anchors.py`. `exercised`: research §10.
- Each toolkit edit gets a change file via `python3 ~/agent-evals/bin/build_changes.py new "<title>" --by claude-code/claude-fable-5-1 --root /home/brandon/dotfiles/docs/changes`, then `python3 ~/agent-evals/bin/build_changes.py`. `declared-only`: lane brief.

## External Contracts

- **Claude Code PreToolUse hook**: stdin JSON with `session_id`, `transcript_path`, `tool_name`, `tool_input`; a deny is `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": ...}}` on stdout with exit 0, as `script_utils.pre_tool_use_deny` writes it. Invariant: a non-zero exit other than 2 or malformed stdout is ignored, so the gate exits 0 on every path. Breaks: a crash with exit 2 blocks the user's cancel. `declared-only` until a TaskStop event is captured after wiring (no TaskStop hook exists today).
- **Claude Code subagent registry**: `<projects dir>/<project>/<session>/subagents/agent-<id>.jsonl` plus `agent-<id>.meta.json` with `agentType`, `parentAgentId`, `spawnDepth`, `finished`. A TaskStopped agent's transcript ends in a `user` record whose text starts `[Request interrupted by user` and its meta has no `finished` key. Invariant: `finished: true` is written only at a normal end. Breaks: a child that neither finishes nor is interrupted reads as live until the next harness write. `exercised`: research §4, real transcripts under `~/.claude/projects/`.
- **`handback_store` rows**: `record(session_id, kind, agent_id=..., **fields)` and `was_recorded(session_id, agent_id, kind)`; new kind constant `KIND_TASKSTOP_DENIED = "taskstop_children_denied"` owned by `fork_children.py`. Invariant: one row per deny; readers compare against the constant. `exercised`: `open_child_gate.DENIED_KIND` uses the same pattern.
- **start.json** (`phase_start.START_FILE`): `{"head": str, "dirty": {path: hash|null}, "holder": {"session": str, "cwd": str} | null, "sessions": [str, ...], "started_at": float | null}`. `phase_start.py` writes the file once per call through `write_text_atomically`. When a record is kept, it keeps `head`, `dirty`, `started_at` and a non-null `holder`; it sets `holder` when the kept one is null and another session is live now, and adds this session's id to `sessions` if missing. `started_at` is the epoch time the record was first written for the run. `read_start_record` returns all five keys; a record written before this change has no `holder`, `sessions` or `started_at` and reads as `None`, `[]`, `None`; a key present with the wrong type raises `StartRecordError`, naming the file and the expected shape. `exercised`: Phase 2 tests.
- **review-scope.json**: the file name `SCOPE_FILE` moves to `code_wait.py`; `code_review_start` imports it with its other `from code_wait import ...` names, so `code_review_start.SCOPE_FILE` still resolves. `ReviewScope` (NamedTuple) gains three trailing fields, each defaulting to `()`: `held_changed`, `held_untracked`, `held_targeted`. An old file still reads through `read_scope`, and the three positional constructions in `tests/scripts/test_code_review_start.py` (:210, :225, :612) still build. `code_wait.HELD_CHANGED_FIELD = "held_changed"` is the key `code_wait` reads; a test asserts it is in `ReviewScope._fields`. No reader under `review/` constructs `ReviewScope` (`rg "ReviewScope("`). `exercised` at step 16c.
- **Holder row claim text**: one format, built only by `code_review_start.held_claim(origin, cwd)` as `f"{origin}; session in {cwd}"`. `origin` is one of three constants in `code_review_start.py`: `DIRTY_UNCHANGED = "dirty at the run start, unchanged now"`, `DIRTY_CHANGED = "dirty at the run start, changed since"`, `UNTRACKED_UNATTRIBUTED = "untracked, written by no recorded coder of this run"`. `cwd` is the holder's cwd: the recorded holder, or the session live at review when no holder is recorded. Readers are the `held-by` prompt line and the scope notes. `holder_row` is imported from `review/review_loop_prompt_file.py:64`, out of bounds and unchanged. `tests/scripts/test_review_loop_script.py:136-137` hold literal claims as fixtures and do not read this text. `exercised`: research §6.
- **Review prompt header lines added by `code_review_start.review_prompt`**: the loop's `read_prompt` stores every `key: value` line and reads only the keys it knows, so these lines reach the prompt file and the loop ignores them: `tool fault: <code_wait.held_fault_text(paths)>` when `held_changed` is not empty; `held files this phase names: <path>, ...` when `held_targeted` is not empty. The keys are constants `TOOL_FAULT_KEY` and `HELD_TARGETED_KEY` in `code_review_start.py`; neither collides with a key in `review_loop_prompt_file.py`. `exercised`: `read_prompt` (review_loop_prompt_file.py:76-90).
- **Tool-fault text**: one owner, `code_wait.held_fault_text(paths)`, returning `"held files changed during the phase (by the coder or by the session that holds them); review left them out, so check them: " + ", ".join(paths)`. Three users: the prompt header line, the scope note (`"Tool fault: " + text`) and the `code_wait` line (`"Tool fault: " + text`).
- **`~/.claude/skills/code/phase-end-block.md`**: read by the fork at the phase-end trigger; reached by opencode through the stow link of `~/.claude/skills/`. No opencode port of `code-fork.md` or `/code` step text exists, so nothing else to patch. `exercised`: research §11.

## Approach

**Item 1 (scripts/code, lib).** `fork_children.py` composes existing readers: `code_wait.agent_transcript` to find the fork transcript, `open_child_gate.live_children` for launch-derived ids, a sibling `*.meta.json` scan for `parentAgentId == fork id` not `finished_by_meta`, then drops ids whose transcript is `agent_finished` or `agent_interrupted`. The loop stop requires three facts: pid alive, `process_group.command_line(pid)` contains `code_review_start.py`, and the fork transcript's `script_utils.bash_commands` holds a `code_review_start.py` command. Output is one JSON object:

```
{"fork": "<id>", "children": ["<agent id>", ...], "unresolved_launches": ["<tool_use_id>", ...],
 "loop": {"pid": <int|null>, "stopped": <bool>, "reason": "none|stopped|gone|not_this_run|not_review_loop"}}
```

Exit 0 with the report, 2 for a usage error, a missing transcript or a non-fork id. The `hook` verb passes (exit 0, no output) when `tool_name != "TaskStop"`, `task_id` is not an agent id, the transcript is missing, the type is not `open_child_gate.CODE_FORK`, no child and no unresolved launch is live, the fork was denied once already, or `CLAUDE_SKIP_HOOKS` is set. Deny reason: `code fork <id> has live children: <ids>. Run python3 ~/.claude/scripts/code/fork_children.py <id>, TaskStop each id it names, then TaskStop the fork.` An unresolved launch is listed as `launch <tool_use_id> (no agent id yet)`. Any exception prints `fork-children-hook: skipped, <exc>` to stderr and exits 0 (fail-open; the cancel must never be blocked by a broken gate).

**Item 2 (scripts/code, lib).**

`phase_start.py` records `holder`, `sessions` and `started_at` as in External Contracts; moves `review-scope.json` aside to `review-scope.prev.json` next to the other `move_aside` calls, so a later phase never reads an earlier phase's scope; `recorded_dirty_files(repo, base_commit)` returns every recorded dirty path sorted, or `None` with no record, keeping today's base check; `changed_dirty_files(repo, record)` returns the paths whose `worktree_snapshot.file_hash` differs from `record["dirty"]` (a deleted file counts as changed).

`code_review_start.phase_held_files`: with a recorded holder, it holds every recorded path less the earlier-phase files, each claim `DIRTY_CHANGED` or `DIRTY_UNCHANGED` with the recorded holder's cwd. With no recorded holder it keeps today's rule exactly: only same-bytes paths, only while another session is live at review, claim `DIRTY_UNCHANGED`. `held_changed` is the held paths that `changed_dirty_files` names. `held_targeted` is the held paths this phase's section names, from the new `expected_red.phase_own_paths(plan_lines, phase)`; they stay held.

`foreign_untracked(repo, record, holder_cwd)` runs only when there is a holder cwd. Candidates are the `??` paths from `worktree_snapshot.status_codes`, less the start.json `dirty` keys, the earlier-phase files and the files under the plan folder (`plan_format.outside_plan_folder`). From those it removes every path a recorded coder wrote: for each id in `record["sessions"]` it reads `session_registry.session_subagents_dir(id)`, takes each `agent-*.meta.json` whose `agentType` is in `script_utils.CODERS` and whose transcript mtime is at or after `record["started_at"]` (no filter when that is `None`), and collects `loop_transcript.written_paths` of the transcript, made repo-relative. What remains is held with claim `UNTRACKED_UNATTRIBUTED`. One note names the paths: `code_review_start: held untracked files no recorded coder of this run wrote (a file an earlier review round's fix coder made is among them until the loop records its writes): <paths>`. When a session id has no subagents folder, the note adds `no coder transcripts found for session <id>`, and the files stay held.

`review_scope` fills the three new fields. `review_prompt` writes the two new header lines. `main` passes the scope fields to `review_prompt` on both the computed route and the `--scope-file` route, so the prompt file the detached child writes carries them.

`code_wait.held_fault_line(repo)` reads only `phase_dir(repo) / SCOPE_FILE`, as plain JSON, through no import of `code_review_start`. It returns `""` when the file is absent or the field is empty; on an unreadable file or a field of the wrong type it returns a line that names the file and the error; it never calls `sys.exit`. `follow_run` prints it after `print_ended_loop` on the phase route only (`launched_folder is None`). The exit code is unchanged.

**Item 3 (skills/code, agents, docs).** Byte-for-byte move of `## Phase-Complete Block` (SKILL.md:100-157) to `skills/code/phase-end-block.md`; the phase-boundary step (SKILL.md:66-72) reads that file at the trigger. Cuts and rewords listed in Phase 3. Anchor rows re-hashed with `rule-anchors.sh`.

## Dependencies

- No new packages.
- Internal: `review/open_child_gate.py`, `review/handback_store.py` (imported, not edited), `lib/loop_transcript.py`, `lib/process_group.py`, `lib/session_registry.py`, `lib/worktree_snapshot.py`, `lib/script_utils.py`, `lib/expected_red.py`, `lib/plan_format.py`, `code/code_wait.py`, `code/phase_start.py`, `code/code_review_start.py`, `tools/rule-anchors.sh`, `~/agent-evals/bin/rule_meter.py` and `bin/rule_meter_scenarios.json`, `~/agent-evals/bin/build_changes.py`.

## Implementation Plan

## Phase 1: fork_children.py, the interrupted reading and the cancel route

### Overview

Ship the command and the hook that name a stopped code fork's live children, and the transcript reading that tells an interrupted child from a live one.

### Changes Required:

#### 1. Interrupted reading

**File**: `claude/.claude/scripts/lib/loop_transcript.py`
**Changes**: add `INTERRUPT_PREFIX = "[Request interrupted by user"` and `agent_interrupted(transcript_path) -> bool`: read the tail with `script_utils.transcript_tail_lines(transcript_path, 65536)`, take the last non-blank record, return True when its `type == "user"` and a `message.content` text block starts with the prefix; False for a missing file. The two interrupt text shapes in real subagent transcripts are `[Request interrupted by user]` and `[Request interrupted by user for tool use]`; in every stopped transcript the interrupt record is the last record.

#### 2. The script

**File**: `claude/.claude/scripts/code/fork_children.py` (new)
**Changes**: `sys.path` lines for `lib/` and `review/`; `fork_meta(transcript)`; `child_ids(fork_transcript, fork_id) -> (children, unresolved)` as described in `## Approach`; `stop_loop(repo, fork_transcript) -> {"pid", "stopped", "reason"}` using `code_wait.running_review_pid(repo)`, `process_group.pid_is_alive`, `process_group.command_line` (a `ProcessQueryError` maps to `not_review_loop`), `process_group.terminate_group` (False maps to `gone`); `KIND_TASKSTOP_DENIED`; `main` with argparse dispatching `hook` or `<fork id> [--repo PATH]` (`--repo` defaults to cwd; the id must match `code_wait.AGENT_ID`).

#### 3. Cancel route and its anchor row

**Files**: `claude/.claude/skills/code/SKILL.md` (line 3 only in this phase), `docs/rule-anchors.md` (the `skills/code/SKILL.md | (preamble)` row, today `5bcfdcf0`), `tests/scripts/test_guidance_rules.py`
**Changes**: extend the cancel sentence: keep the current text and add one sentence after it: "When it does not stop, run `python3 ~/.claude/scripts/code/fork_children.py <fork id>` and TaskStop each child it names, then the fork." The pin at test_guidance_rules.py:184-191 stays as it is, and a second `assertIn` pins the added sentence. In this same phase, run `bash claude/.claude/scripts/tools/rule-anchors.sh list claude/.claude/skills/code/SKILL.md` and put the new preamble hash in place of `5bcfdcf0`; add this phase's change-file link to the row's evidence cell. The added sentence is metered in Phase 3 step 4.

#### 4. Tests

**Files**: `tests/scripts/test_fork_children.py` (new; script path from `FORK_CHILDREN_SCRIPT`, default `toolkit_paths.CODE_DIR / "fork_children.py"`; `HANDBACK_STORE_DIR` and `CLAUDE_CONFIG_DIR` pointed at temp dirs), `tests/scripts/test_loop_transcript.py` (add cases; create if absent), `tests/scripts/test_guidance_rules.py` (cancel pin :184-191 retargeted to the new phrase)
**Changes**: cases listed under Success Criteria. Fixtures reuse `tests/scripts/test_open_child_gate.py` helpers (`launch`, `launch_result`, `notification`, `ASYNC_RESULT`). The hook stdin fixture is a transcript TaskStop `tool_input` (`{"task_id": "a…"}`) plus the standard PreToolUse fields, with a note that a captured event replaces it after wiring.

#### 5. Timing and change file

**Files**: scratchpad script `/tmp/claude-1000/-home-brandon-dotfiles-code-skill-nov22/51a3d3bc-5d29-40a4-a641-8124f736f3b7/scratchpad/time_fork_children.sh`; `docs/changes/notes/2026-11-22-a-stopped-code-fork-s-live-children-are-named-and.md` (new, through `build_changes.py new`)
**Changes**: 30 runs each of the hook on a pass fixture, the hook on a deny fixture and `python3 -c pass`; the three medians go in the change file. Evidence line: the 2026-11-22 cancel was the main session running TaskStop on the fork directly; TaskStop returned success and named no children; the coder kept running and rewrote a deleted file. Watch line: settings.json wiring pending at agent-evals-c3.

### Success Criteria

- `agent_interrupted` is True for each of the two interrupt text shapes, False for a normal last assistant record, False for an interrupt record that is not the last record, False for a missing file. The two interrupt text shapes in real subagent transcripts are `[Request interrupted by user]` and `[Request interrupted by user for tool use]`; in every stopped transcript the interrupt record is the last record.
- The hook denies a TaskStop of a code fork with one live coder and names the id; a second call on the same fork passes.
- The hook passes for a `b…` task id, a non-fork agent type, a fork whose child finished by meta, and a fork whose child's last record is the interrupt.
- The hook passes for a fork whose only launched coder's transcript ends on each interrupt shape (`[Request interrupted by user]`, `[Request interrupted by user for tool use]`), and denies the same fork while that transcript ends on an assistant record.
- AC2 ("a replay of a cancel during the coder step writes nothing after the stop") has no automated test: a fixture holds it by construction. The coverage table maps AC2 to the manual AC20 run only; the interrupted-reading unit test stays as coverage for `agent_interrupted`.
- A child named only by `parentAgentId` in its meta (no launch result in the fork transcript) is listed.
- CLI JSON matches the shape above; `loop.reason` is `none` with no pid file; with a fake loop (`python3 -c` whose argv holds `code_review_start.py`, pid file under `code_wait.phase_dir`, matching bash command in the fork fixture) `stopped` is true and the process exits; with a live pid but no `code_review_start.py` command in the fork transcript, `reason` is `not_this_run` and the process stays alive.
- Malformed stdin gives exit 0 and stderr starting `fork-children-hook: skipped`.

#### Automated Verification:

- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_fork_children.py` (RED now: no file)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_loop_transcript.py` (RED now: no `agent_interrupted`)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_guidance_rules.py` (RED once the second pin is added, until line 3 carries the sentence)
- [ ] **Presence**: `rg -q "fork_children.py" claude/.claude/skills/code/SKILL.md` (RED now)
- [ ] **Anchors**: `bash claude/.claude/scripts/tools/rule-anchors.sh check && python3 tests/parallel_tests.py test_rule_anchors.py` (green now; must be green at the end of this phase, with the preamble row re-hashed)
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/code/fork_children.py claude/.claude/scripts/lib/loop_transcript.py`
- [ ] **Agent-run**: the timing script's three medians are recorded in `docs/changes/notes/2026-11-22-a-stopped-code-fork-s-live-children-are-named-and.md`

#### Manual Verification:

- [ ] **Manual-verified (AC20; covers AC2, a replay of a cancel during the coder step writes nothing after the stop)**: in a live session, dispatch a code fork on a scratch plan and let it launch a coder. From the main session, run `python3 ~/.claude/scripts/code/fork_children.py <fork id>`; the JSON names the coder id. TaskStop that id, then the fork. Run `git status --porcelain` in the scratch repo right after, and again 60 s later: the output is the same, so nothing was written after the stop. Human-only until the settings line lands: with the hook wired, TaskStop on the fork is denied once, with the same id.

---

## Phase 2: hold every start-dirty path, name changed held files, hold foreign untracked files

### Overview

With a holder recorded at the phase start, the review scope holds every file recorded dirty at the run start for the whole phase, names a changed held file as a tool fault, and holds untracked files no recorded coder of the run wrote.

### Changes Required:

#### 1. Start record

**File**: `claude/.claude/scripts/code/phase_start.py`
**Changes**: `start_record` adds `"holder"` (from `session_registry.other_live_session_in(repo, own id)`, stored as `{"session": session_registry.holder_label(row), "cwd": row["cwd"]}`, or `null`), `"sessions"` (`[own id]`) and `"started_at"` (`time.time()`). `read_start_record` returns the five keys, defaulting the three new ones for an old record, and raises `StartRecordError` on a wrong type. `main` builds the record to write on every route: the kept route (same HEAD, or `--resume` with an ancestor head) keeps `head`, `dirty` and `started_at`, adds this session's id to `sessions`, keeps a non-null `holder` and fills a null one from `other_live_session_in` now; the fresh route makes everything new. `main` writes once through `write_text_atomically`, then prints the same base it prints today. With `CLAUDE_CODE_SESSION_ID` unset it records no holder and adds no session, and stderr says `phase_start: CLAUDE_CODE_SESSION_ID is not set, so no holder or session is recorded`. Add `move_aside(run_folder, code_wait.SCOPE_FILE, code_wait.PREVIOUS_SCOPE_FILE)` next to the other three calls. Rename `unchanged_dirty_files` to `recorded_dirty_files(repo, base_commit) -> list[str] | None`, returning `sorted(dirty)` with today's base check. Add `changed_dirty_files(repo, record) -> list[str]`. Update the module docstring: the record's five keys, and that start-dirty files are held for the phase when a holder is recorded. Callers: `rg -n "unchanged_dirty_files"` must list only `code_review_start.py` and `tests/scripts/test_code_review_start.py`; a hit under `scripts/review/` stops the phase (out of bounds).

#### 2. Session, transcript and phase-path readers

**Files**: `claude/.claude/scripts/lib/session_registry.py`, `claude/.claude/scripts/lib/loop_transcript.py`, `claude/.claude/scripts/lib/expected_red.py`
**Changes**: `session_subagents_dir(session_id) -> Path | None` (first match of `projects_dir().glob(f"*/{session_id}/subagents")`); `written_paths(transcript_path) -> set[str]` over `script_utils.tool_use_calls`, collecting `file_path` of Write and Edit and `notebook_path`/`file_path` of NotebookEdit; `phase_own_paths(plan_lines, phase_id) -> list[str]` as `sorted(section_paths(plan_lines, plan["sections"].get(str(phase_id))))`, placed next to `earlier_phase_paths` (`later_phase_paths` and `earlier_phase_paths` leave the current phase out by design, and no reader returns the current phase's own paths).

#### 3. Review start

**File**: `claude/.claude/scripts/code/code_review_start.py`
**Changes**: add the three claim origins and `held_claim(origin, cwd)` from External Contracts; every holder row this file builds uses `held_claim`. `phase_held_files` returns `(holders, held_changed, held_targeted)`, following the `## Approach` rule for a recorded holder and for no recorded holder; when `held_changed` is not empty: `held_note(notes, "Tool fault: " + code_wait.held_fault_text(held_changed))`; when `held_targeted` is not empty: `held_note(notes, "code_review_start: this phase's plan names held files, which stay held, so the phase's change to them is not reviewed: <paths>")`. Add `foreign_untracked(repo, record, holder_cwd, plan, phase, notes) -> list[holder row]` as in `## Approach`, with no folder expansion. `review_scope` adds the untracked rows to `holders`, so they leave the handoff `files:` list and `phase_changed`, and fills `held_changed`, `held_untracked` and `held_targeted`. `review_prompt` gains `held_changed=()` and `held_targeted=()` and writes the `tool fault:` and `held files this phase names:` header lines after the `held-by` line. `main` passes `scope.held_changed` and `scope.held_targeted` to `review_prompt`. Update docstring lines 17-19 to name the hold rule and the two new header lines.

#### 4. Phase-route fault line

**Files**: `claude/.claude/scripts/code/code_wait.py`, `claude/.claude/scripts/code/code_review_start.py` (import only)
**Changes**: move `SCOPE_FILE = "review-scope.json"` from `code_review_start.py` into `code_wait.py`; add `PREVIOUS_SCOPE_FILE = "review-scope.prev.json"` and `HELD_CHANGED_FIELD = "held_changed"`; add `SCOPE_FILE` to `code_review_start.py`'s existing `from code_wait import ...` line (no new import in either direction, so no cycle). Add `held_fault_text(paths)` (External Contracts). Add `held_fault_line(repo) -> str`: reads `phase_dir(repo) / SCOPE_FILE` with `json.loads`; no file gives `""`; an `OSError` or `ValueError`, a top level that is not an object, or a field that is not a list of strings gives `f"code_wait: {scope_file} could not be read for held-file faults ({problem}); check the held files by hand."`; an empty or absent field gives `""`; otherwise `"Tool fault: " + held_fault_text(paths)`. In `follow_run`, right after `code = print_ended_loop(run)`, add `if launched_folder is None:` then `fault_line = held_fault_line(repo)` and print it when non-empty. `print_ended_loop`, `phase_review` and the return codes are unchanged; the launched `--loop` route never reads the file.

#### 5. Shared handoff text and its anchor row

**Files**: `claude/.claude/skills/_shared/handoff-block.md` (line 28), `docs/rule-anchors.md` (row `78d7b13d`, `skills/_shared/handoff-block.md | ## Who writes \`files\` for \`/code\``)
**Changes**: replace the parenthetical after "less the held files" with: "(with a session other than the run's live in the repo at a phase start or at review, every file dirty at the run start per `phase_start.py`'s start record, and any untracked file no recorded coder of the run wrote; a file the plan gives to an earlier phase is never held)". The rest of the sentence is unchanged. In this same phase, run `bash claude/.claude/scripts/tools/rule-anchors.sh list claude/.claude/skills/_shared/handoff-block.md`, put the new hash in place of `78d7b13d`, and add this phase's change-file link to the row. The reworded sentence is metered in Phase 3 step 4.

#### 6. Tests

**Files**: `tests/scripts/test_phase_start.py`, `tests/scripts/test_code_review_start.py`, `tests/scripts/test_code_wait.py`, `tests/scripts/test_loop_transcript.py`, `tests/scripts/test_expected_red.py`
**Changes**:

`test_phase_start.py`: new record cases: with a live other session registered, a fresh `phase_start` writes `holder` with that session's label and cwd, `sessions == [own id]` and a numeric `started_at`; a second call from another session id on the same HEAD keeps `head`, `dirty`, `started_at` and `holder`, and appends the new id; `--resume` appends its id; an old record without the new keys reads with defaults; a record with `"sessions": "x"` raises, with the expected shape in the message; `review-scope.json` is moved to `review-scope.prev.json`. The :211 flip: register the other session before `phase_start`, edit shared.py, then unregister the other session before review; shared.py is still held (whole-phase hold); the claim is `dirty at the run start, changed since; session in {repo}`; the dry-run prompt holds the `tool fault:` line naming shared.py. Update the :226 claim to `dirty at the run start, unchanged now; session in {repo}`. No recorded holder: with no session live at review, nothing is held; with one live at review, same-bytes files are held as today.

`test_code_review_start.py`: repoint the patches at :432, :471, :482 and :525 to `recorded_dirty_files`, which now return the new tuple shape where `phase_held_files` is patched; update the claims at :444 and :588 to the one format. Detached prompt file: run `main` on the `--scope-file` route with a scope whose `held_changed == ["shared.py"]` and `held_targeted == ["mine.py"]`, capture the prompt file through the `write_script_prompt` capture helper at :130-140, and assert the prompt file text holds `tool fault: held files changed during the phase (by the coder or by the session that holds them); review left them out, so check them: shared.py` and `held files this phase names: mine.py`. AC11: a plan whose current phase names a recorded dirty path, with a recorded holder; the path is in `held files:`, in `held files this phase names:` and in the scope notes line `this phase's plan names held files`, and not in the handoff `files:` list. Untracked cases (fake `CLAUDE_CONFIG_DIR/projects/p/<id>/subagents/` with `agent-<id>.jsonl` and `.meta.json`): (a) a foreign untracked file is held, with claim `untracked, written by no recorded coder of this run; session in {cwd}`, and the note names it; (b) a file written by a coder transcript (agentType `coder`) of a recorded session is reviewed; (c) a file written by a coder of a second recorded session (a resume) is reviewed; (d) with no recorded holder and no session live at review, the untracked file is reviewed; (e) an untracked path in start.json `dirty` appears in one holder row only; (f) a file written by a `code-reviewer` transcript is held, because the agent type is not a coder; (g) a recorded session with no subagents folder holds the file, and the note names `no coder transcripts found for session <id>`; (h) a coder transcript older than `started_at` does not attribute. A test asserts `code_wait.HELD_CHANGED_FIELD in code_review_start.ReviewScope._fields`.

`test_code_wait.py`: phase route, with the scope file holding `held_changed: ["a.py"]`: stdout ends with `Tool fault: ... check them: a.py`, and the exit code equals the code without the file; no scope file: no line, and no `SystemExit`; a scope file that is not JSON: the `could not be read for held-file faults` line, exit code unchanged; launched `--loop` route, with a stale phase scope file present: no fault line.

`test_loop_transcript.py`: `written_paths` covers Write, Edit and NotebookEdit and ignores Bash. `test_expected_red.py`: `phase_own_paths` returns the current section's paths, not an earlier or later phase's. Leave `tests/scripts/test_review_loop_script.py:136-137` as they are.

#### 7. Change file

**File**: `docs/changes/notes/2026-11-22-code-hold-dirty-and-foreign-untracked.md` (new, through `build_changes.py new`)
**Changes**: Result states that a coder edit to a held file is named in the scope note and the code_wait output as a tool fault; the packet's `tool_fault` field is unchanged (out of bounds).

### Success Criteria

- With a holder recorded at phase start, a start-dirty file edited before review is held, even after the holder session ends. Its claim reads `changed since`, and the detached prompt file holds the `tool fault:` line.
- A held file unchanged since the start is held with no fault line.
- A held file that this phase's section names is held and listed on `held files this phase names:` and in the scope notes.
- Under a holder, an untracked file no recorded session's coder wrote is held and named; one a recorded coder wrote is reviewed, from any recorded session; with no holder, every untracked file is reviewed as before.
- `code_wait review` prints the fault line after the packet on the phase route only. It prints nothing and never exits when there is no scope file.

#### Automated Verification:

- [ ] **Presence**: `rg -q "def check_record_base" claude/.claude/scripts/code/phase_start.py` (RED now; `check_record_base(repo, base_commit, record)` is the single-read replacement for `recorded_dirty_files`, ruled in ledger block 10)
- [ ] **Ban**: `! rg -q "unchanged_dirty_files" claude/.claude/scripts tests/scripts` (RED now)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_phase_start.py` (RED after the :211 flip)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_code_review_start.py` (RED: detached prompt file and untracked cases)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_code_wait.py` (RED: no `held_fault_line`)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_loop_transcript.py test_expected_red.py` (RED: no `written_paths`, no `phase_own_paths`)
- [ ] **Presence**: `rg -q "any untracked file no recorded coder of the run wrote; a file the plan gives to an earlier phase is never held" claude/.claude/skills/_shared/handoff-block.md` (RED now)
- [ ] **Anchors**: `bash claude/.claude/scripts/tools/rule-anchors.sh check && python3 tests/parallel_tests.py test_rule_anchors.py` (green now; must be green at the end of this phase, with row `78d7b13d` re-hashed)
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/code/phase_start.py claude/.claude/scripts/code/code_review_start.py claude/.claude/scripts/code/code_wait.py claude/.claude/scripts/lib/session_registry.py claude/.claude/scripts/lib/loop_transcript.py claude/.claude/scripts/lib/expected_red.py`

#### Manual Verification:

- [ ] **Manual-verified**: with a second live session registered in a scratch repo, dirty one tracked file and create one untracked file before `phase_start.py`, edit the tracked file, run `code_review_start.py`; the prompt header names the tracked file as changed-since and the untracked file as written by no recorded coder of this run.

---

## Phase 3: /code trim, phase-end file, stop-rule owners, anchors, meter runs

### Overview

Cut the /code load by the structure move and the metered cuts, give each stop rule one owner, turn the two dense paragraphs into lists, and record the counts.

### Changes Required:

#### 1. Phase-end file

**Files**: `claude/.claude/skills/code/phase-end-block.md` (new), `claude/.claude/skills/code/SKILL.md`
**Changes**: move the whole `## Phase-Complete Block` section (SKILL.md:100-157, Blocks B and C and the /stage line) byte for byte into the new file; at SKILL.md:66-72 replace "then print the matching Phase-Complete Block" with "then Read `~/.claude/skills/code/phase-end-block.md` and print the matching block" (metered).

#### 2. Cuts and owners

**Files**: `claude/.claude/skills/code/SKILL.md`, `claude/.claude/agents/code-fork.md`
**Changes**: cut the second "do not mark the phase done" at :91/92 (6 words, exact duplicate); keep code-fork.md:8-9 and cut SKILL.md:24's overlap (8 words, metered); cut SKILL.md:34's restatement of global CLAUDE.md:26 after a meter run shows no drop, keeping every phrase pinned in test_guidance_rules.py:29-56; :20 owns STOP and never-end-the-run, :26 and :74 keep only their own clauses ("Never call AskUserQuestion" stays at :26; the ":74 never commits" pin stays); convert :34 (plan impacts) and :94 (converged bullet) to lists, one branch per item, same words where pins require them. Any word change is metered.

#### 3. Anchors and tests

**Files**: `docs/rule-anchors.md` (the SKILL.md rows and new phase-end-block.md rows), `tests/scripts/toolkit_paths.py` (`CODE_PHASE_END_FILE`), `tests/scripts/test_guidance_rules.py` (:205-211 retargeted to `guidance_text` of phase-end-block.md), `tests/scripts/test_code_skill_text.py` (:25-27 counts "Commit subject: <subject>" across SKILL.md plus phase-end-block.md, at least 3; new test that SKILL.md names `phase-end-block.md` in the phase-boundary step and holds no `## Phase-Complete Block`)
**Changes**: run `bash claude/.claude/scripts/tools/rule-anchors.sh list` on `claude/.claude/skills/code/SKILL.md`, `claude/.claude/skills/code/phase-end-block.md` and `claude/.claude/agents/code-fork.md`. In `docs/rule-anchors.md`: drop the SKILL.md `## Phase-Complete Block` row; re-hash every SKILL.md row whose block this phase changed, including the preamble row as Phase 1 left it; add rows for each heading block of phase-end-block.md, with this phase's change-file link. Phase 2's handoff-block row is not touched again unless this phase edits that file.

#### 4. Meter runs

**Files**: `~/agent-evals/bin/rule_meter_scenarios.json` (check `git -C ~/agent-evals status --short bin/` first and stop if dirty; commit that file alone, then pull_keep_index and push). The file is a dict keyed by scenario id; each entry has `name`, `rule_text`, `rule_source` (absent on 14 entries whose rule lives outside the tree), `setup`, `detector`, `task` and a `suffix` map with `supportive`, `neutral` and `competing` keys. No entry has `rule_source` `skills/code/SKILL.md`, `agents/code-fork.md` or `skills/_shared/handoff-block.md` yet. A `detector` names a `detect_<name>` function in `rule_meter.py` or a script in `bin/rule_meter_checks/`; reuse an existing detector when its read fits, else a new script under `bin/rule_meter_checks/` with a unittest beside the existing check tests, committed with the scenarios in one agent-evals commit; `rule_meter.py` stays untouched; a detector reads the fork's output text only, never the repo state (agent-evals-c3 ruling, 2026-11-22).
**Changes**: sentences metered: the cancel route (Phase 1), handoff-block.md:28 (Phase 2), the phase-end trigger, the :24 cut, the :34 restatement cut, each stop-rule edit at :26 and :74, each word-changing list item. Run `python3 ~/agent-evals/bin/rule_meter.py run-all --rule <id>` then `summary`; per-arm counts go in the change file. Before a run check `free -g`; under 8 GB free, wait and tell agent-evals-c3.

#### 5. Change file and sweep

**File**: `docs/changes/notes/2026-11-22-the-code-phase-complete-blocks-move-to-a-file-read.md` (new, through `build_changes.py new`)
**Changes**: records 14 duplicate words cut (6 + 8), the Phase-Complete move (about 375 of 3033 words), the four start-load counts before and after (`skills/code/SKILL.md`, `skills/_shared/modifiers.md`, `skills/_shared/plan-reading.md`, `skills/_shared/handoff-block.md`; before 3033, 114, 205 and 476, total 3828; limit 3488) as printed by `skill_word_band.py`, the meter counts, the fold of rank 1011, and the ticket's wrong premise (exact in-load duplicates measured at 14 words, not 150-250). Sweep: `rg -n "Phase-Complete Block|unchanged_dirty_files|fork_children" claude docs tests`; state that no opencode port of code-fork.md or the /code step text exists.

#### 6. Start-load word checker

**Files**: `tests/scripts/skill_word_band.py` (new), `tests/scripts/test_skill_word_band.py` (new; script path from `SKILL_WORD_BAND_SCRIPT`)
**Changes**: usage `python3 tests/scripts/skill_word_band.py <limit> <file> [<file> ...]`. For each file it prints `<words> <path>`, counted with `str.split()` items, a bare list marker (`-`, `*`, `+`, `<digits>.`) not counted, then `<total> total (limit <limit>)`. Exit 1 when the total is above the limit; exit 2 on a missing file or a limit that is not an integer, with a message naming the problem. Tests: under, at and above the limit; missing file; bad limit. Budget for the coder: the move and the two exact cuts remove about 389 words; Phase 1's added cancel sentence (about 20 words), the phase-end trigger (about 6) and Phase 2's handoff-block rewording (about 10) add about 36 back; so the :34 restatement cut and the stop-rule dedupe must remove at least about 30 words. If a meter run keeps a cut and the total stays above 3488, stop and report AC15 as failing. Do not trim unmetered text to make the count.

### Success Criteria

- `SKILL.md` holds no `## Phase-Complete Block` heading and names `phase-end-block.md` at the phase-boundary step.
- The text /code loads at start (SKILL.md, `_shared/modifiers.md`, `_shared/plan-reading.md`, `_shared/handoff-block.md`) totals at most 3488 words, down from 3828 (limit ruled in block 12).
- The change file records the four counts before and after.
- Each pinned phrase in the three text-pin test files is still found, or its pin was retargeted to the file that now owns it.
- Every anchored block hashes clean.
- Each reworded sentence has on/off counts in the change file.

#### Automated Verification:

- [x] **Presence**: `test -f claude/.claude/skills/code/phase-end-block.md`
- [x] **Ban**: `rg -q "^## Phase-Complete Block" claude/.claude/skills/code/SKILL.md` has no match
- [x] **Presence**: `rg -q "phase-end-block.md" claude/.claude/skills/code/SKILL.md` finds the trigger
- [x] **Count** (total 3442 with the meter skipping bare list markers, limit 3488): `python3 tests/scripts/skill_word_band.py 3488 claude/.claude/skills/code/SKILL.md claude/.claude/skills/_shared/modifiers.md claude/.claude/skills/_shared/plan-reading.md claude/.claude/skills/_shared/handoff-block.md`
- [x] **Test-verified**: `python3 tests/parallel_tests.py test_skill_word_band.py` (RED now)
- [x] **Test-verified**: `python3 tests/parallel_tests.py test_guidance_rules.py test_code_skill_text.py test_rule_anchors.py`
- [x] **Anchors**: `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [x] **Agent-run**: rule-meter per-arm counts for every metered sentence recorded in `docs/changes/notes/2026-11-22-the-code-phase-complete-blocks-move-to-a-file-read.md`

#### Manual Verification:

- [ ] **Manual-verified**: run `/code` on a one-phase scratch plan to its first phase end; the fork reads `phase-end-block.md` and prints Block B with the commit subject line.

---

## Phase 4: Close pass

`/close-branch`: scripts first; four report-only reviewers in parallel on the whole branch diff (correctness, structure, test intent, and plan and acceptance-criteria reconciliation); one `coder` that fixes every finding and writes every owed test; a report-only gate on the fix diff alone; the recap sheet. Root-cause rule: a cast or default that papers over a fixable loose structure is a finding; fix the source.

### Changes Required:

#### 1. Bounds checker

**Files**: `tests/scripts/branch_bounds.py` (new), `tests/scripts/test_branch_bounds.py` (new; script path from `BRANCH_BOUNDS_SCRIPT`)
**Changes**: usage `python3 tests/scripts/branch_bounds.py <base-sha> <head-sha>`. It reads `git diff --name-only <base>..<head>` and the work tree's `git status --porcelain --untracked-files=all` paths. It exits 1, listing each offending path, when a path starts with `claude/.claude/scripts/review/` (this covers `claude/.claude/scripts/review/verify-prep`, named in the message when hit) or `claude/.claude/scripts/gates/`, equals `claude/.claude/scripts/code/plan_check.py` or `claude/.claude/settings.json`, or has a basename of `CLAUDE.md` or `orchestration.md`. Exit 2 on a bad sha. Tests: a scratch repo with one commit per offending shape, plus a clean commit.

#### 2. Close fixes

**Files**: whatever the close-pass findings name, inside the bounds above.
**Changes**: per `/close-branch`.

### Success Criteria

Quality checks green; every reviewer finding fixed, shown wrong, or (an ask that changes a ticket AC) put to the user through agent-evals-c3; the fix-diff gate passed; every acceptance criterion mapped to a test or explicitly retired (AC2, a replay of a cancel during the coder step writes nothing after the stop, maps to manual AC20); concentration counts stated; recap and smoke-test checklist delivered. With no open finding, a coder writes one line of evidence under each open item.

#### Automated Verification:

- [ ] **Suite**: `bash tests/run.sh`
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_branch_bounds.py` (RED now: no file)
- [ ] **Scope box**: `test -n "$(git diff --name-only <base-sha>..<head-sha>)"`, with the two recorded commit ids filled in at close
- [ ] **Bounds**: `python3 tests/scripts/branch_bounds.py <base-sha> <head-sha>` (RED now: no checker)

#### Manual Verification:

- [ ] N/A (close pass)

## Plan Deviations

- 2026-11-22, code-skill-nov22 lane: the Phase 3 change file is `docs/changes/notes/2026-11-22-the-code-phase-complete-blocks-move-to-a-file-read.md` (the name `build_changes.py new` generated; the file exists) in place of `2026-11-22-code-skill-trim-and-phase-end-file.md` in "#### 5. Change file and sweep"; no acceptance criterion changes.
- 2026-11-22, orchestrating session agent-evals-c3, relayed by the code-skill-nov22 lane: ruling on Ticket #AC15 (the ticket carries no number; AC15 of the trim item): the limit becomes 3488 words, the measured start load, in place of 3445; recorded in `03-decisions.md` block 12 with the meter counts.
- 2026-11-22, orchestrating session agent-evals-c3, relayed by the code-skill-nov22 lane: ruling on Ticket #AC15 (the trim item): the word meter does not count a bare list marker; the four start-load counts become 2647 / 110 / 201 / 484 = 3442 against the limit 3488; recorded in `03-decisions.md` block 12 addendum.
- 2026-11-22, orchestrating session agent-evals-c3, relayed by the code-skill-nov22 lane: ruling on Ticket #AC15 (trim item) and #AC17: AC15's duplicate clause is narrowed to the 6 exact-duplicate words already cut (SKILL.md:24 stays as a paraphrase); AC17's one-owner clause is held, with no stop-rule dedupe; recorded in `03-decisions.md` block 13.

## Acceptance Criteria

- **Criteria file**: `docs/plans/code-skill-1122/acceptance-criteria.md`

The Close pass reconciles every id against the real suite, matching behavior, not markers. A covering test asserts at the public boundary a caller reaches (the script CLI, the hook stdin, the prompt text), never an internal function.

## What We're NOT Doing

- Wiring `fork_children.py hook` in `settings.json`: the line goes to agent-evals-c3 at branch end. Item 1's first AC is reported as pending wiring until it lands.
- The packet `tool_fault` field and `review_loop_held` wording (scripts/review, out of bounds).
- Rank-1011 bullet 4 (the acceptance_criteria-none duplicate in coder-core and code-reviewer:85): split to queue item `dedupe-the-acceptance-criteria-none-rule-across` by agent-evals-c3 ruling, 2026-11-22.
- Sentences shared only with `review-fork-run.md`; any edit to review-fork-run.md, orchestration.md, a CLAUDE.md or plan_check.py.
- Splitting `script_utils.py`, folding `code_wait.agent_transcript` with `session_subagents_dir`, a shared constant for the `note_changed` wording: refactor candidates, not on this branch.

## Edge Cases

- No-op hold: a recorded holder, and every held file is unchanged. Rows are held, there is no `tool fault:` line, `held_changed` is `()`, and `code_wait` prints nothing.
- Holder ends mid-phase: the hold stays (ledger block 9a). The claim names the recorded cwd.
- Holder recorded at a later phase start: a holder first recorded at Phase 2's start holds the run-start dirty files from then on, because the record keeps the run-start `dirty` map.
- Old start.json mid-run: it reads with defaults (no holder, so today's rule applies). The next `phase_start` call adds the keys.
- Resume in a new session: its id is appended, so coders from both sessions attribute.
- A file the loop's fix coder made in an earlier round: held, with the untracked note (ledger block 9b trade-off).
- Stale scope file: moved aside by `phase_start`. The launched route never reads it.
- Untracked plan-folder files: never candidates, because the review already drops them.
- Earlier-phase untracked files: not held. Plan-named files go through `earlier_phase_files`, and unnamed ones through the `started_at` filter on their coder transcript.

## Testing Strategy

Each script change ships with a test that fails without it, in the existing test file for that script. Hook behavior is tested through stdin fixtures at the CLI boundary. Prose changes are pinned by the three text-pin files and measured by rule-meter on/off runs. `bash tests/run.sh` and `bash tests/lint.sh` on every changed `.py` file before hand-over; the real diff size is reported against the architect's revised estimate of about 1430 lines (stop and report above 2860).

## References

- ./00-ticket.md, ./02-research.md, ./03-decisions.md
- `docs/toolkit-script-rules.md`, `claude/.claude/scripts/CLAUDE.md`
- Architect plan: subagent `a9f311c006d93905b`, 2026-11-22
