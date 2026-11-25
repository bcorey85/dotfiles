# Seven review-loop defects of 2026-11-23

> Ticket: ./00-ticket.md
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-23

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

Seven fixes to the /code review loop and its ask tools, one per phase. A relayed ruling takes a session id as well as a name. A session may reject an ask for a wanted change to a user-only file. A capped packet opens its asks, so a session's rejection is stored and a fresh run drops the re-filed ask, and a lane session is told `--by session`. A capped packet and its stop name the fix rounds (never above 2) and the post-cap passes by kind. Reviewer dispatch lines name their round and role, and a later round's lines come back from the same wait call. A fix pass that goes against an accepted ruling is put back and the run stops. A /code resume that changed source cannot write its stop until a review loop ran. Each behavior change gets a change file.

## Phase Status

<!-- Hoisted from below so the first screen answers "where are the agents?". The one section that changes after writing (/code ticks it) — source of truth for "which phase is next". Do not move it back down. -->

- [x] Phase 1: Relay a ruling by session id (risk: low)
- [x] Phase 2: A session rejects a wanted change to a user-only file (risk: high)
- [x] Phase 3: A capped packet opens its asks; a lane is told `--by session` (risk: high)
- [x] Phase 4: Fix rounds and post-cap passes in the packet and stop (risk: low)
- [ ] Phase 5: Round and role on reviewer dispatch lines (risk: low)
- [ ] Phase 6: Put back a fix pass that breaks an accepted ruling (risk: high)
- [ ] Phase 7: A /code resume diff must get a review (risk: high)
- [ ] Phase 8: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

Seven independent slices with no shared surface: each phase owns its own contract, so Phase 0 is omitted on purpose, and Phase 1 is the walking skeleton.

## Decisions

- D7. Relay lookup — `session_registry.row_for_session_id`; `--relayed-by` matches a live `sessionId` first, then a name; the ruling rows record the row's name. Trade-off: a nameless live row cannot relay.
- D5. Session rejects — a session `rejected` passes on a user-only wanted-change ask only; a revert ask, a criteria ask and every session accept stay refused (agent-evals-c3-owner, 2026-11-23; narrows ticket AC 5).
- D4. Post-cap passes — `iter` and `review_round` unchanged; new packet keys `fix_rounds` and `post_cap_passes`, owned by `review/review_loop_post_cap.py`, with one summary line.
- D3. Round-2 dispatch — end-to-end test first; each dispatch line names its round and role; later-round lines print from the same `code_wait.py review` call.
- D2. Capped asks — `record_open` opens a cap-reached packet's asks; `effective_status` stays the owner of clean; `asks_done_line` prints `--by session` in a lane.
- D1. Ruling check — one `ruling-check` model call per fix pass in a ruled run; on `against` the pass is put back and the run stops `critical-blocker` with `against_ruling`.
- D6/G1. Resume review — gate on the code-fork's stop.md Write through `fork_write_scope`, with `resume.json` owned by `code/resume_review_gate.py`. Trade-off: a fork that skips `phase_start.py --resume` or never writes stop.md escapes.
- G2. Four pass kinds: `final read`, `class closure`, `prose repair`, `scoped re-review`.
- G3. An accepted ask on a capped packet is recorded, and applied by the resume.
- G4. The ruling check covers the run's own rulings; no store walk.
- Q1. Rejected-ask rows stay per session.

## Approaches Considered and Not Taken

- Renumber `review_round` to count fix rounds: breaks packet identity, the ledger iter join and relaunch `--iter`.
- Judge rulings with a `drop:` grammar and a regex: every real ruling row is free prose, so it parses none.
- Gate a /code resume on SubagentHandback: 405 of 512 real /code forks never call it.
- Let any session reject of a user-only ask pass: lets a session keep a coder's CLAUDE.md edit through a revert ask.

## Constraints

- Script rules (`docs/toolkit-script-rules.md`, `claude/.claude/scripts/CLAUDE.md`): snake_case; one owner per fact; `bash tests/lint.sh <files>` passes; tests under `tests/scripts/` with paths from `toolkit_paths.py`, run through `python3 tests/parallel_tests.py <file>`; a hook gate states fail-open or fail-closed in a comment. `exercised`.
- Sizes (`wc -l`, `exercised`): `review/review_fix.py` 999, `review/review_fix_asks.py` 978, `review/review_loop_script.py` 973. None gains a verb, route or state field; new logic goes in new modules. Phase 3 moves `asks_done_line` out of review_fix.py first.
- Off-limits: calibration_guard.py, calibration_lock.py, mutation_lock.py, refactor_flow.py, refactor_log_input.py, and the close-branch and refactor SKILL.md files. settings.json and every CLAUDE.md are not edited. `declared-only` (lane brief).
- `review_round` and `iter` keep their meaning: `handback.py` INTEGER_KEYS, `ask_row_fields`, `review_fix.py:485`, `review_fix_names.py` PACKET_IDENTITY_KEYS read them. `exercised` (research).
- `ROUND_BUDGET = 2` at `review_loop_script.py:145`. `exercised`.
- `phase_start.py` moves `loop-dir` aside on every start, `--resume` included (`phase_start.py:249-253`), and `code_review_start.py:654` writes it. A `loop-dir` file in the run folder therefore means a review loop started in this run. `exercised`.
- A /code fork's hook events carry `agent_type` `code-fork` (`claude/.claude/skills/code/SKILL.md:5`; 1738 subagent meta files with `"agentType":"code-fork"`). Only 107 of 512 real /code fork transcripts call SubagentHandback. `exercised` (architect's sweep).
- User-only ask kinds (`review/approval_asks_store.py`): a revert ask's change reads "revert the fix coder's edit to `<path>`" (:16-17); a wanted-change ask's change ends with `wanted_edit_target(path)` (:62); a criteria ask carries `CRITERIA_KEY`. `exercised`.
- Change files: `python3 ~/agent-evals/bin/build_changes.py new "<title>" --by claude-code/claude-opus-5-5`, then `python3 ~/agent-evals/bin/build_changes.py`. Sign-offs stay in `03-decisions.md`.
- Domain terms: use the glossary's `round budget` and `relayed ruling`. The packet keys `fix_rounds` and `post_cap_passes` are field names, not glossary terms; no glossary entry is added.

## External Contracts

- No provider, API or platform contract is touched. None.
- Internal invariants with a wide blast radius:
  - The hook JSON contract of `gates/fork_write_scope.py` (hook JSON in, `permissionDecision` out or exit 2) is unchanged; omp's `claude-security-bridge.ts` keeps working. `declared-only` until Phase 7's tests run.
  - Packet keys are added, never renamed: old packets lack `fix_rounds`, `post_cap_passes` and `against_ruling`, and a reader gives None for a missing `fix_rounds` (the cap line then leaves the count out) and [] for the two lists (G6). `declared-only` until Phase 4 and 6's `test_handback.py` run.
  - `--relayed-by <name>` keeps working for a name one live row holds. `declared-only` until Phase 1's tests run.
  - `user_only_refusal` keeps its refusal for every caller that passes no outcomes. `declared-only` until Phase 2's tests run.

## Approach

Each phase is one vertical slice: the owner change, its callers, the skill sentence it needs, and a test that fails on master. New modules: `review/review_loop_post_cap.py` (Phase 4), `review/review_loop_ruling_check.py` (Phase 6), `code/resume_review_gate.py` (Phase 7). Owners extended in place: `lib/session_registry.py`, `lib/human_turn_lookup.py`, `review/approval_asks_store.py`, `review/review_asks.py`, `lib/lane_entries.py`, `review/reviewer_dispatch.py`, `gates/fork_write_scope.py`. The ruling check follows the `closure_check` pattern (`review_loop_closure.py:117` with `reply_with_one_retry`, `review_loop_findings.py:299`). Put-back uses `lib/file_backup.py`. Tree identity uses `lib/reviewed_tree.py` `reviewed_fingerprint`.

## Dependencies

- External packages: none.
- Internal: `lib/session_registry.py` `live_session_rows`, `row_for_name`; `lib/human_turn_lookup.py`; `review/ruling_relay.py`; `review/review_fix_plan_impacts.py`; `review/approval_asks_store.py`; `review/review_asks.py` `user_only_refusal`, `ruler_of_ask`; `review/phase_asks.py`; `review/capped_review.py` `effective_status`; `review/handback.py` `CLEAN_STATUSES`; `lib/lane_entries.py` `all_entries`; `review/review_loop_calls.py` `claude_call`; `lib/file_backup.py`; `lib/reviewed_tree.py`; `lib/script_utils.py` `write_text_atomically`; `code/code_wait.py` `LOOP_DIR_FILE`, `phase_dir`; `lib/stop_file_names.py` `STOP_FILE`; tests `ReviewLoopHarness` and `FAKE_CLAUDE` in `tests/scripts/test_review_loop_script.py`.

## Implementation Plan

Paths are relative to the worktree root. `S` = `claude/.claude/scripts`, `K` = `claude/.claude/skills`, `T` = `tests/scripts`. Line anchors are from the tree at planning time; re-check them as earlier phases land. Every phase ends with one change file (see Constraints) whose `test:` names the phase's failing-before test, and reports its real diff size against its estimate.

### Phase 1: Relay a ruling by session id

#### Overview

`--relayed-by` takes a live session id as well as a name, and the ruling rows record the row's name. Estimate: 45 source + 70 test lines.

#### Changes Required:

##### 1. Live row by id

**File**: `S/lib/session_registry.py`
**Changes**: add `row_for_session_id(session_id)`: the one live row whose `sessionId` equals the argument, else None. Name it in the module docstring.

##### 2. The lookup

**File**: `S/lib/human_turn_lookup.py`
**Changes**: replace `session_id_of_name` (:31) with `relaying_row(word)` returning `RelayingSession(session_id, name)`. Order: `row_for_session_id(word)` first; a row with an empty name refuses with `the live row of session id {word} holds no name; name the session, then relay`. Then name matches: several refuse with `{n} live sessions are named {word!r} in {dir}; relay by the session id of one of them instead: --relayed-by <sessionId>`; none refuses with `no live session has the id or the name {word!r} in {dir}`. `verified_human_turn(word, after_epoch)` (:113) returns `(RelayingSession, HumanTurn)`; its refusal texts name `session.name`. Update the docstring at :9.

##### 3. The writers

**Files**: `S/review/ruling_relay.py`, `S/review/review_fix_plan_impacts.py`, `S/lib/ask_outcome_words.py`, `K/_shared/review-fork-run.md`
**Changes**: `RelayedRuling` (:35) gains `session_name`; `verify_relay` (:86) unpacks the pair; `record_relay` writes `relayed.session_name`; the `RelayRequest` docstring says "name or id". `review_fix_plan_impacts.py:104` and `:124` use `relayed.session_name`. `ask_outcome_words.py:33`: `RELAY_USAGE = f"{RELAYED_BY_FLAG} <session name or id>"`. `review-fork-run.md:34`: "`--relayed-by <session name>` (or the session id when two live sessions share the name)".

##### 4. Tests

**Files**: `T/test_session_registry.py`, `T/test_human_turn_lookup.py`, `T/test_ruling_relay.py`, `T/test_review_fix_plan_impacts.py`
**Changes**: id lookup; two live rows share a name: the name refuses and the text holds `--relayed-by <sessionId>`, the id of one is accepted (fails on master); a nameless id row refuses; a relay by id records the row's name in the `ask-ruling-relayed` row; the plan-impact owner line names the session name for an id relay. Edge: an id of a dead session refuses; an empty `--relayed-by` keeps the existing refusal (`ruling_relay.py:50`).

#### Success Criteria

A relay by the id of one of two same-named live rows is accepted and records that row's name; a relay by the shared name refuses and names the id form.

#### Automated Verification:

- [ ] **Test-verified**: relay tests pass — `python3 tests/parallel_tests.py test_session_registry.py test_human_turn_lookup.py test_ruling_relay.py test_review_fix_plan_impacts.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/lib/session_registry.py claude/.claude/scripts/lib/human_turn_lookup.py claude/.claude/scripts/review/ruling_relay.py claude/.claude/scripts/review/review_fix_plan_impacts.py claude/.claude/scripts/lib/ask_outcome_words.py`

#### Manual Verification:

- [ ] N/A (library code with full test coverage)

---

### Phase 2: A session rejects a wanted change to a user-only file

#### Overview

D5: a session `rejected` on a user-only wanted-change ask passes in `phase_asks.py rule` and asks-done; a revert ask, a criteria ask and every session accept stay refused. Estimate: 40 source + 80 test lines.

#### Changes Required:

##### 1. Wanted-change reader

**File**: `S/review/approval_asks_store.py`
**Changes**: add `wanted_path_of_change(change)`, the reader for `wanted_edit_target` (:62): the path when the text ends with that form, else None. Plain `endswith`/`rfind`, no regex.

##### 2. The refusal owner

**File**: `S/review/review_asks.py`
**Changes**: `user_only_refusal(asks, ruler, user_command, holdable=False, outcomes=None)` (:226): with `outcomes` given, a user-only ask whose outcome is `rejected`, with no `CRITERIA_KEY`, and whose `wanted_path_of_change(item["change"])` is not None is left out of the refused numbers. The `listed`/`reasons` lines name only the refused asks. `ruler_of_ask` (:247) is unchanged.

##### 3. The callers

**Files**: `S/review/phase_asks.py`, `S/review/review_fix_asks.py`, `S/lib/ask_outcome_words.py`, `K/_shared/review-fork-run.md`
**Changes**: in `rule_open_asks` (:338) the user-only check runs after `read_rulings` parses: `ruler_of_call` keeps only `split_ruler`, and `review_asks.user_only_refusal(asks, call.ruler, user_command, outcomes=[o for o, _ in rulings])` runs next; the relay check stays before it. Update the docstring at :8-10. `review_fix_asks.py:732` `refuse_session_on_user_only` gains `outcomes=None` and passes it on; `:758` and `:836` pass the outcomes they hold (net +2 lines). `ask_outcome_words.rule_instruction` (:57) takes a required precomputed flag, which phase_asks computes at both call sites (:175, :212), with no default argument (G14), and, when every user-only ask is a wanted-change ask, adds "a session may reject a wanted change itself; only an accept needs the user". `_shared/review-fork-run.md:37` (G10): in a `--by session` call, a user-only wanted-change ask may be `rejected`; any other outcome stays `held`. That line is a rule change: give its change file rule-meter on/off runs per ~/agent-evals/CLAUDE.md, or an `unmeasured` note.

##### 4. Tests

**Files**: `T/test_phase_asks.py`, `T/test_review_fix_ask_ruler.py`
**Changes**: a `wanted_ask(path)` helper whose change ends with `wanted_edit_target(path)`. For each of `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`: a session `rejected` logs a row with `decided_by: session` (fails on master); a session `accepted` is refused and logs nothing. The :842 test is kept, renamed `test_a_session_ruling_on_a_revert_ask_is_refused_and_logs_nothing`. A criteria ask with a session reject is refused. A mixed batch (wanted reject plus revert reject) is refused, naming only the revert ask. asks-done `--by session` with `rejected` on a wanted ask is accepted, and on a revert ask refused.

#### Success Criteria

A session `rejected` on a user-only wanted-change ask to CLAUDE.md, CLAUDE.local.md or AGENTS.md is logged; a session `accepted` on it, and a session reject of a revert ask, are refused and log nothing.

#### Automated Verification:

- [ ] **Test-verified**: ask ruling tests pass — `python3 tests/parallel_tests.py test_phase_asks.py test_review_fix_ask_ruler.py test_review_asks.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/review/approval_asks_store.py claude/.claude/scripts/review/review_asks.py claude/.claude/scripts/review/phase_asks.py claude/.claude/scripts/review/review_fix_asks.py claude/.claude/scripts/lib/ask_outcome_words.py`

#### Manual Verification:

- [ ] N/A (library code with full test coverage)

---

### Phase 3: A capped packet opens its asks; a lane is told `--by session`

#### Overview

A session's rejection on a cap-reached packet is stored, so a fresh run drops the re-filed ask; the asks-done line in a lane says `--by session`. Estimate: 50 source + 130 test lines.

#### Changes Required:

##### 1. Open capped asks

**File**: `S/review/phase_asks.py`
**Changes**: `record_open` (:153) opens the asks when `capped_review.effective_status(packet, repo)` is in `CLEAN_STATUSES` or the packet status is cap-reached. Opening never writes a status. Update the docstring.

##### 2. Lane check

**File**: `S/lib/lane_entries.py`
**Changes**: add `is_lane_session(session_id)`: True when any entry of `all_entries` (:175) has that `session_id`. It raises what `all_entries` raises.

##### 3. Move and widen the asks-done line

**Files**: `S/review/review_asks.py`, `S/review/review_fix.py`
**Changes**: move `asks_done_line` (review_fix.py:343-368) into review_asks.py; review_fix.py imports it at its two call sites (:376, :616). It prints `plan_format.SESSION_RULING` when `lane_entries.is_lane_session(os.environ.get("CLAUDE_CODE_SESSION_ID", ""))`, else `plan_format.USER_RULING`. On `LaneFileError` or `OSError` it prints `--by user` and writes `review_fix: lane files unreadable (<error>); the asks-done line names --by user` to stderr. In the session form the user-only clause reads "give `held` for user_only ask(s) N unless the ask is a wanted change you reject". Before the change, confirm on one real lane fork transcript under `~/.claude/projects` that `CLAUDE_CODE_SESSION_ID` in a fork's Bash is the lane's own session id, and report the result.

##### 4. Skill text

**File**: `K/code/SKILL.md`
**Changes**: line 99 (`cap-reached`): when code_wait printed finding asks, run `phase_asks.py list` and rule them as for `converged`, dispatch no coder for an accepted ask (list it under `Asks decided`: the resume applies it), then STOP and report the `cap reached after ...` line. The Resume paragraph (:32) gains the step that applies an accepted capped ask (listed under `Asks decided`) through the fix launch (G11). That hunk stays inside the Resume paragraph (fix/code-gates-nov23 also edits SKILL.md). It is a rule change: give its change file rule-meter on/off runs, or an `unmeasured` note.

##### 5. Tests

**Files**: `T/test_phase_asks.py`, `T/test_phase_asks_chain.py`, `T/test_lane_entries.py`, `T/test_review_asks.py`, `T/test_review_fix_script.py`
**Changes**: (a) pin (passes on master; AC2's fails-before test is (b)): a session-rejected ask on a converged packet; a fresh loop run (same session id) whose reviewer raises the same ask drops it. (b) a capped packet: `record_open` opens its asks; `rule rejected:...` writes the `ask-rejected` row; a fresh `ReviewLoopHarness` run whose reviewer raises the same ask lists it under `dropped_asks` and ends with no stop (fails on master). (c) `is_lane_session`. (d) with a lane entry whose `session_id` is the env session id, the cap-reached stop output prints `asks-done --by session`; with none, `--by user` (fails on master); unreadable lane files print `--by user` and the stderr line. (e) after a session ruling on a capped packet, `capped_review.effective_status` still reads not clean (AC14, G11).

#### Success Criteria

A session's rejection on a cap-reached packet is stored and a fresh run drops the same ask with no stop; a lane session's stop prints `--by session`.

#### Automated Verification:

- [ ] **Test-verified**: capped-ask and lane tests pass — `python3 tests/parallel_tests.py test_phase_asks.py test_phase_asks_chain.py test_lane_entries.py test_review_asks.py test_review_fix_script.py test_code_skill_text.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/review/phase_asks.py claude/.claude/scripts/lib/lane_entries.py claude/.claude/scripts/review/review_asks.py claude/.claude/scripts/review/review_fix.py`

#### Manual Verification:

- [ ] N/A (library code with full test coverage)

---

### Phase 4: Fix rounds and post-cap passes in the packet and stop

#### Overview

The packet gains `fix_rounds` (never above `ROUND_BUDGET`) and `post_cap_passes` (ordered kinds); the cap-reached stop and code_wait print `cap reached after N fix round(s); post-cap passes: ...`. Estimate: 90 source + 110 test lines. — atomic: the packet keys, their writer and their reader change together, or the packet drops them.

#### Changes Required:

##### 1. The owner module

**File**: `S/review/review_loop_post_cap.py` (new)
**Changes**: kind constants `FINAL_READ = "final read"`, `CLASS_CLOSURE = "class closure"`, `PROSE_REPAIR = "prose repair"`, `SCOPED_REREVIEW = "scoped re-review"`. Mixin `PostCapPasses` with `fix_rounds = 0`, `post_cap_passes = ()`, `count_fix_round()` (calls `self.next_round()`, adds 1 to `fix_rounds`) and `post_cap_round(kind)` (calls `self.next_round()`, appends `kind`). `cap_summary_line(packet)` reads plain dict keys and returns `cap reached after <n> fix round(s); post-cap passes: <kinds>` (`none` when empty), or None for a packet without the keys. Standard library only.

##### 2. The loop

**Files**: `S/review/review_loop_script.py`, `S/review/review_loop_final_read.py`, `S/review/review_loop_packet.py`, `S/review/handback.py`
**Changes**: `LoopRun` gains the mixin; `walk` (:937) calls `count_fix_round()`; :838 calls `post_cap_round(CLASS_CLOSURE)`, :886 `post_cap_round(PROSE_REPAIR)`; `outcome()` (:890) adds `fix_rounds` and `post_cap_passes` (net about +4 lines). `read_diffs` (:54) takes a `kind` and calls `post_cap_round(kind)` in place of `next_round` (:67); `read_last_fix` passes `FINAL_READ`, `read_late_repairs` passes `SCOPED_REREVIEW`. `EMPTY_OUTCOME` (:105) gains `"fix_rounds": 0, "post_cap_passes": []`. `review_loop_packet.packet_message` (:60-97) writes both keys into `fields`, and `handback.read_header` (:325-360) reads `fix_rounds` into the header (G5). `review_loop_main.py` (:157) seeds `fix_rounds` (capped at ROUND_BUDGET) and `post_cap_passes` from the prior header, as it seeds `iter_count` (G7). handback.py: the keys join SCRIPT_PACKET_KEYS (:77), INTEGER_KEYS (:115), LIST_KEYS (:81) and STRING_LIST_KEYS (:85).

##### 3. The readers

**Files**: `S/review/review_fix.py`, `S/code/code_wait.py`, `K/code/SKILL.md`, `T/fixtures/packets/review-loop-cap-reached.txt`
**Changes**: review_fix.py `stop_for_status` (:599): for cap-reached, insert `cap_summary_line(packet)` first (one import, one line). code_wait.py `follow_run` phase route (:615-628): after `print_ended_loop`, on a cap-reached packet print `cap_summary_line`; read the packet once, shared with `phase_asks_notice` (:331). SKILL.md:99: report that line as the round count, never `review_round` or `iter`. The fixture gains both keys.

##### 4. Tests

**Files**: `T/test_review_loop_script.py`, `T/test_review_fix_script.py`, `T/test_code_wait.py`, `T/test_handback.py`
**Changes**: a harness run with two full rounds that file fixes, then a final read that files a fix, a class closure, a prose repair and a late-repair read: packet `fix_rounds == 2`, `post_cap_passes` lists the kinds in walk order, `scoped re-review` included (AC6, G8), and the printed line holds `after 2 fix round(s)` and no round number above 2 (fails on master). A run that converges in round 1 then closes a class: `fix_rounds == 1`, no summary line. The cap stop line in review_fix; the line after a cap-reached packet in code_wait; the new keys parse in handback, a bad type is refused, and an old packet without them prints no summary line. Assert on the packet read back through handback, never only on the in-memory outcome (G5). A relaunch whose header holds `fix_rounds: 2` reports 2, not the relaunch's own count (G7).

#### Success Criteria

A loop that hits the two-round cap and then runs post-cap passes reports `fix_rounds: 2` with the passes by kind, and its stop text says `cap reached after 2 fix round(s)` with no round count above the cap.

#### Automated Verification:

- [ ] **Test-verified**: post-cap tests pass — `python3 tests/parallel_tests.py test_review_loop_script.py test_review_fix_script.py test_code_wait.py test_handback.py test_code_skill_text.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/review/review_loop_post_cap.py claude/.claude/scripts/review/review_loop_script.py claude/.claude/scripts/review/review_loop_final_read.py claude/.claude/scripts/review/review_loop_packet.py claude/.claude/scripts/review/handback.py claude/.claude/scripts/review/review_fix.py claude/.claude/scripts/code/code_wait.py`

#### Manual Verification:

- [ ] N/A (library code with full test coverage)

---

### Phase 5: Round and role on reviewer dispatch lines

#### Overview

Each `ACTION: dispatch-reviewer` block names its round, and each line its role; a later round's lines print from the same `code_wait.py review` call. Estimate: 35 source + 120 test lines.

#### Changes Required:

##### 1. End-to-end test first

**File**: `T/test_code_wait.py`
**Changes**: a main-mode loop (REVIEWERS_MAIN); round 1 answered through `code_wait.py review <id> <report>` with fake finished transcripts; the fake fix coder edits a file; the same call is rerun until the round-2 manifest exists. Assert the output holds `round 2:` and each round-2 role (`review2-code-reviewer`, ...) with its report file. Fails on master. If round-2 lines never print on the rerun call, fix `follow_run` so each poll reads `open_reviewer_requests(run)`, and record that as the defect.

##### 2. The lines

**Files**: `S/review/reviewer_dispatch.py`, `S/code/code_wait.py`, `K/code/SKILL.md`
**Changes**: `write_round` (:75) stores `round` in each entry; `all_requests` (:140) fills a missing entry `round` from its manifest (old manifests). `request_lines` (:156) groups by round: a heading `round <n>: dispatch these <k> reviewer(s) now; earlier rounds' reports are already in`, then `- round <n>: <role>; agent ...` per entry, keeping a `-2` role suffix; `open_request_lines` adds the same prefix. `code_wait.py` `reviewer_dispatch_lines` (:546) adds "a later round's lines come back from this same call". `_shared/review-fork-run.md:13` describes the new line shape (G9). SKILL.md:94: "A later round prints its own `round <n>:` lines from the same `code_wait.py review` call: dispatch them as new agents under those roles."

##### 3. Tests

**Files**: `T/test_reviewer_dispatch.py`, `T/test_review_fix_script.py`, `T/test_waiting_review_launch.py`, `T/test_code_wait.py`
**Changes**: the label format; an old manifest without `round` in its entries. Update the 14 asserts that pin the old line shape (test_waiting_review_launch 3, test_reviewer_dispatch 6, test_code_wait 3, test_review_fix_script 2, from `rg -c '"- agent |ACTION: dispatch-reviewer' tests/scripts`) (G9).

#### Success Criteria

After a round-1 fix pass, the fork's wait call prints the round-2 reviewers by round and role; a round-2 wait on reports nobody was told to write fails the test on master.

#### Automated Verification:

- [ ] **Test-verified**: dispatch tests pass — `python3 tests/parallel_tests.py test_reviewer_dispatch.py test_code_wait.py test_review_loop_script.py test_code_skill_text.py test_review_fix_script.py test_waiting_review_launch.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/review/reviewer_dispatch.py claude/.claude/scripts/code/code_wait.py`

#### Manual Verification:

- [ ] N/A (library code with full test coverage)

---

### Phase 6: Put back a fix pass that breaks an accepted ruling

#### Overview

After each fix pass of a run that holds a ruling, a `ruling-check` model call judges the pass against the rulings; on `against` the pass is put back and the run stops `critical-blocker` with `against_ruling`. Estimate: 150 source + 160 test lines.

#### Changes Required:

##### 1. The check

**File**: `S/review/review_loop_ruling_check.py` (new)
**Changes**: mixin `RulingCheck` and `RulingBrokenError(RuntimeError)`, whose message is the blocker: `fix pass <call> went against the accepted ruling on <file>: <ruling>; it kept: <kept>. The pass was put back.`
- `begin_ruling_check(call_name, paths)`: None when the run holds no ruling (`user_ruled`, `session_ruled` and `adopted` all empty); else `file_backup.save_files(self.repo, paths, self.out / "ruling-check" / call_name)`, keeping the set of paths absent before the pass.
- `check_rulings_kept(call_name, findings, result, backup)`: returns at once with no backup or no `result.changed`. The rulings are `issue_text` of this pass's ruled findings plus the header-ruled texts (`user_ruled` and `adopted` are accepted rulings; `session_ruled`, set at `review_loop_ruled.py:261`, holds both outcomes, so the prompt tags each text with its source key only, with no outcome tag (G12)), deduplicated. The prompt names them and the pass diff (written to `self.out / "ruling-check" / call_name / "pass.diff"`) and asks for `{"verdicts": [{"ruling", "verdict": "kept"|"against", "file", "kept"}]}` through `reply_with_one_retry(claude_call, "ruling-check", ..., model="sonnet", tools="Read,Grep")`. On any `against`: `file_backup.restore_changed(backup)`, unlink the changed paths absent before the pass, `self.keep_open(findings)`, set `self.against_ruling`, raise `RulingBrokenError`. Else `file_backup.discard(backup)`. A reply that does not parse after one retry raises `ReplyShapeError`; catch it and `ModelCallError`, and turn both into the existing tool-fault stop (G12). The pass is not put back, and the blocker says so. A path `file_backup` could not save is named in the blocker as not put back.

##### 2. Wiring

**Files**: `S/review/review_loop_script.py`, `S/review/review_loop_main.py`, `S/review/review_loop_packet.py`, `S/review/handback.py`
**Changes**: `repair` (:572): `ruling_backup = self.begin_ruling_check(call_name, self.pass_scope(files_in_scope))` before `coder_call`: the backup covers every file the pass may write (G13), and `self.check_rulings_kept(call_name, findings, result, ruling_backup)` after `check_pass_result` (:626); `LoopRun` gains the mixin; `outcome()` adds `against_ruling` (about +4 lines). `review_loop_main.py:210`: `RulingBrokenError` joins the critical-blocker tuple. `EMPTY_OUTCOME` gains `"against_ruling": []`; `packet_message` writes it into `fields` (G5); handback.py LIST_KEYS and SCRIPT_PACKET_KEYS gain it.

##### 3. Tests

**Files**: `T/test_review_loop_script.py`, `T/test_handback.py`
**Changes**: FAKE_CLAUDE's key line gains `ruling-check`; with no `ruling-check` key in a scenario the fake replies all-kept, so existing tests keep passing. New test: a resume header with a session-ruled accepted finding whose ruling says "drop the prefix strip"; the fake coder edits the file but keeps the strip; the fake judge returns `against`. Assert the file is byte-equal to its pre-pass text, a second file the pass wrote inside `pass_scope` but outside `files_in_scope` is put back too (G13), the packet is `critical-blocker` with `against_ruling` naming the file, and no reviewer round ran after the check (fails on master). A `kept` verdict changes nothing. A run with no ruling makes no `ruling-check` call. A judge reply that does not parse ends in the tool-fault stop with the pass left in place (G12).

#### Success Criteria

A fix pass that keeps code an accepted ruling dropped is put back byte-for-byte and the run stops `critical-blocker` with `against_ruling`; a pass that keeps the ruling moves on.

#### Automated Verification:

- [ ] **Test-verified**: ruling-check tests pass — `python3 tests/parallel_tests.py test_review_loop_script.py test_handback.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/review/review_loop_ruling_check.py claude/.claude/scripts/review/review_loop_script.py claude/.claude/scripts/review/review_loop_main.py claude/.claude/scripts/review/review_loop_packet.py claude/.claude/scripts/review/handback.py`

#### Manual Verification:

- [ ] N/A (library code with full test coverage)

---

### Phase 7: A /code resume diff must get a review

#### Overview

G1: `phase_start.py --resume` records the resume base; the code-fork's Write of `stop.md` is denied once when the tree moved and no review loop started in the run. Estimate: 110 source + 150 test lines.

#### Changes Required:

##### 1. The gate module

**File**: `S/code/resume_review_gate.py` (new)
**Changes**: `RESUME_FILE = "resume.json"`, shape `{"repo", "head", "tree", "at", "denied"}`. `record_resume(run_folder, repo)`: head from `script_utils.head_commit(repo)`, tree from `reviewed_tree.reviewed_fingerprint(repo, base=head)`, one atomic write. `clear_resume(run_folder)`. `resume_deny_reason(stop_path)`: run folder is `stop_path.parent`; None when resume.json is absent (fail-open: not a resume), when `denied` is true, or when `run_folder / code_wait.LOOP_DIR_FILE` exists; else fingerprint `repo` against `head`, None when it equals `tree`; else set `denied: true` (atomic) and return `fork-write-scope: this /code resume changed source since phase_start.py --resume (<n> path(s): <first 5>), and no review loop ran on it. Run step 5 (code_review_start.py ... --base <head>) before the stop; write the stop again only when the run ends before review.` with the changed paths from `script_utils.changed_files(repo, head)` minus notes paths. It raises on an unreadable resume.json or a git failure.

##### 2. Callers

**Files**: `S/code/phase_start.py`, `S/gates/fork_write_scope.py`, `K/code/SKILL.md`
**Changes**: phase_start.py `main` (:245-272): under `--resume`, after the record is written (kept-record branch and fallback), call `record_resume(run_folder, repo)`; without `--resume`, call `clear_resume(run_folder)` beside the `move_aside` calls (:250-253). fork_write_scope.py `write_deny_reason` (:104): for a `file_path` in the run folder named `stop_file_names.STOP_FILE`, return `resume_review_gate.resume_deny_reason(path)` when it gives one, before `pending_launch_reason`; import it lazily inside the code-fork branch; a comment states fail-open with no resume record and fail-closed on a crash (:127-135 exits 2 naming the gate). SKILL.md:32 (Resume): "A resume whose feedback changes files runs step 3's `phase_start.py --resume` before its coder, and step 5's review before any stop, unless the diff is empty."

##### 3. Tests

**Files**: `T/test_phase_start.py`, `T/test_fork_write_scope.py`, `T/fixtures/hook_event_code_fork_write_stop.json`, `T/test_code_skill_text.py`
**Changes**: build the fixture from the PreToolUse Write fields that `test_fork_write_scope.py` already feeds the gate, paths rewritten to the temp repo. fork_write_scope adds `S/code` to `sys.path` to import `resume_review_gate` and `code_wait`. `--resume` writes resume.json with head and tree; a plain start removes it. Cases: (a) `--resume`, a source edit, Write stop.md: denied, text names the file (fails on master); (b) same with `loop-dir` present: allowed; (c) no edit, or notes paths only: allowed; (d) a second stop Write after a deny: allowed; (e) no resume.json: allowed; (f) a non-code-fork agent: allowed; (g) corrupt resume.json: exit 2 naming the gate; (h) a commit between the resume and the stop with no other change: allowed. Pin the Resume sentence.

#### Success Criteria

A /code resume that edits a source file and writes its stop with no review loop is denied once with the changed path named; a resume with a review loop, or with no source change, writes its stop.

#### Automated Verification:

- [ ] **Test-verified**: resume gate tests pass — `python3 tests/parallel_tests.py test_phase_start.py test_fork_write_scope.py test_code_skill_text.py test_code_review_start.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/code/resume_review_gate.py claude/.claude/scripts/code/phase_start.py claude/.claude/scripts/gates/fork_write_scope.py`

#### Manual Verification:

- [ ] N/A (hook code with full test coverage on a captured event)

---

### Phase 8: Close pass

#### Overview

`/close-branch` on the whole branch diff, per `~/.claude/skills/_shared/closing-phases.md`.

#### Success Criteria

Quality checks green; every reviewer finding fixed, shown wrong, or (an ask that changes a ticket AC) put to the user; the fix-diff gate passed; every acceptance criterion mapped to a test or retired; recap and smoke-test checklist delivered.

#### Automated Verification:

- [ ] **Test-verified**: full suite green — `bash tests/run.sh`

#### Manual Verification:

- [ ] Human-only: run the smoke-test checklist from the recap.

## References

- ./00-ticket.md, ./01-questions.md, ./02-research.md, ./03-decisions.md
- `docs/toolkit-script-rules.md`, `claude/.claude/scripts/CLAUDE.md`

## Plan Deviations

- 2026-11-24, session (agent-evals-c3-owner): Phase 2 left review_loop_ruled.py:240 comment ("the approval asks only the user rules") stale; Phase 3 reword it to "the approval asks the session may not rule (anything but a rejected on a wanted-change ask)" when it edits review_fix.py asks_done_line. Changes no acceptance criterion.
- 2026-11-24, lane session (ruling P4-stop, option A): Phase 4's files also include review/review_launch.py, review/review_fix_asks.py and lib/review_fix_names.py (the `--fix-rounds` and `--post-cap-passes` launch flags and their relaunch carry). No AC changed.
