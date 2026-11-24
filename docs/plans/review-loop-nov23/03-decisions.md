# Design Decisions — review-loop-nov23

> Research: ./02-research.md
> Status: 12/12 resolved

The lane session made each choice below under the orchestrator's go-ahead for steps inside this branch (agent-evals-c3-owner, 2026-11-23). D5 narrows AC 5; the criteria owner is `session` (plan_check owner), so agent-evals-c3-owner ruled it.

## Queue

- [x] D7. Relay lookup by session id or name — from backend-architect
- [x] D5. Which session rejects of a user_only ask pass — from backend-architect
- [x] D4. Packet and stop text for post-cap passes — from backend-architect
- [x] D3. Round-2 reviewer dispatch lines — from backend-architect
- [x] D2. Session rejection on a capped packet, and `--by session` in a lane — from backend-architect
- [x] D1. Judge and put back a pass that breaks an accepted ruling — from backend-architect
- [x] D6. Enforce a review of a /code resume diff — from backend-architect
- [x] Q1. Cross-session rejected rows for item 2 — from backend-architect
- [x] G1. Item 6 gate point — DESIGN GAP from backend-architect
- [x] G2. Item 4 pass kinds — DESIGN GAP from backend-architect
- [x] G3. Accepted asks on a cap-reached stop — DESIGN GAP from backend-architect
- [x] G4. Item 1 scope and cost — DESIGN GAP from backend-architect

## Resolved

### 7. Relay lookup by session id or name
- **Choice:** `lib/session_registry.py` gains `row_for_session_id`. `lib/human_turn_lookup.py` resolves the `--relayed-by` word as an exact live `sessionId` first, then as a name, and returns the row's id and name. `RelayedRuling` carries the resolved name, and every writer of `relayed_by` (ruling_relay.py, review_fix_plan_impacts.py) records it. A name held by several live rows still refuses, and the refusal names the id form. A live row matched by id with no `name` refuses. `RELAY_USAGE` reads `--relayed-by <session name or id>`.
- **Reasoning:** session_registry owns live rows. Ids are UUIDs, so an id never collides with a real name. The ticket asks the record to hold the row's name, so a nameless row has nothing to record.
- **Alternatives rejected:** all logic in human_turn_lookup (a second reader of live rows); recording the id for a nameless row (the entry would no longer name a session the user knows).
- **Trade-off accepted:** a nameless live row cannot relay until it is named.

### 5. Which session rejects of a user_only ask pass
- **Choice:** `phase_asks.py rule` (and asks-done, which shares `review_asks.user_only_refusal`) accepts a session `rejected` on a user_only wanted-change ask (the loop already put the file back; its change ends with `wanted_edit_target(path)`). A session `rejected` on a revert ask, a session ruling on a criteria ask, and every session `accepted` stay refused. The refusal moves after the outcomes are parsed so it sees each outcome; the ask kind is read through `approval_asks_store`, never a new regex.
- **Reasoning:** a reject of a wanted change leaves the file as the base has it, so nothing protected changes. A reject of a revert ask keeps a coder's edit to CLAUDE.md, which the user-only rule guards. Sign-off: agent-evals-c3-owner, 2026-11-23, as the orchestrating session for a session-owned criterion (plan_check owner: `session`); it narrows AC 5 to wanted-change asks.
- **Alternatives rejected:** any session reject (lets a session keep a coder's CLAUDE.md edit, and inverts `test_phase_asks.py:842`); a session reject of a revert ask that also restores the blob (changes what reject means).
- **Trade-off accepted:** a revert ask on a user-only file still needs the user.

### 4. Packet and stop text for post-cap passes
- **Choice:** keep `iter` and `review_round` as they are (join keys). Add packet keys `fix_rounds` (full review-and-fix rounds run, never above `ROUND_BUDGET`) and `post_cap_passes` (ordered list of kind names: `final read`, `class closure`, `late repair read`, `scoped re-review`, `prose repair`). A new mixin module `review/review_loop_post_cap.py` owns the kind constants, the recorder called at each post-cap `next_round`, and the one-line formatter "cap reached after N fix rounds; post-cap passes: ...". The cap-reached stop text in review_fix.py prints that line from the packet; code/SKILL.md tells the session to report that line, never `review_round` or `iter`, as the round count. handback.py INTEGER_KEYS and SCRIPT_PACKET_KEYS gain the keys; the cap-reached fixture gains them.
- **Reasoning:** the wrong record came from a session reading `review_round` as a round count. A named field plus a printed line gives it the right number to copy.
- **Alternatives rejected:** renumbering `review_round` (breaks packet identity, the ledger iter join and relaunch `--iter`); skill text only (no test can pin it).
- **Trade-off accepted:** two more packet keys, and review_fix.py (999 lines) gains one import and one call, no verb, route or state field.

### 3. Round-2 reviewer dispatch lines
- **Choice:** first write the end-to-end test (main-mode loop, round-1 reports answered through code_wait, fake fix coder edits code, then the round-2 wait). Each `ACTION: dispatch-reviewer` block names its round and each line its role (`round 2: review2-code-reviewer`). When `code_wait.py review <id> <report>` returns with requests of a later round open, it prints them at once under that round's heading. SKILL.md:94 names that a later round's lines come back from the same call.
- **Reasoning:** the loop already writes round-2 requests; the fork took round-2 lines for round-1 repeats or never read them. A round label in the exit line meets "tells the fork which reviewers to dispatch under which names".
- **Alternatives rejected:** a short wait that exits the loop (leaves round 2 unreviewed, the shape of the sighting); an extra STILL_WORKING message only (does not name the reviewers).
- **Trade-off accepted:** if the end-to-end test shows the scripts already print round-2 lines with names, the fix is the round label and the immediate print, not a new route.

### 2. Session rejection on a capped packet, and `--by session` in a lane
- **Choice:** `phase_asks.py record_open` also opens the finding asks of a cap-reached packet, so a session `rule ... rejected` writes the `ask-rejected` row a fresh run reads. Opening them never changes the packet's status: `capped_review.effective_status` stays the owner of clean. The line that tells a session how to record a ruling (`asks_done_line`, `rule_instruction`) prints `--by session` when the current session id is a lane entry's `session_id` (new reader in `lib/lane_entries.py`), and `--by user` otherwise. Pin the same-session drop with a test; it may already pass.
- **Reasoning:** the confirmed gap is the capped packet: `rule` said "no open asks" and nothing was stored. Lane entries already hold the session id, so the lane check reads one owner.
- **Alternatives rejected:** writing rejected rows from the session's stop prose (no script reads prose); a wider similarity threshold (hides real new asks); always printing both lines (the session still picks wrong).
- **Trade-off accepted:** a capped packet now leaves open phase asks that a session must rule before the next run.

### 1. Judge and put back a pass that breaks an accepted ruling
- **Choice:** after a fix pass whose findings carry an accepted or adopted ruling, one model call (`ruling-check` agent key) reads the rulings and the pass diff and returns JSON: one verdict per ruling (`kept` or `against`, with the ruled text it broke). On `against`, the loop puts the pass's files back through the existing PassGuard/file_backup path and stops as `critical-blocker` with packet key `against_ruling` (ruling, file, what the pass kept). It lives in a new mixin `review/review_loop_ruling_check.py`, called from `check_pass_result`.
- **Reasoning:** rulings are free prose in every real store row, so only a model can judge them. A stop after the put-back meets "puts it back instead of moving on" with the least code.
- **Alternatives rejected:** a `drop:` grammar plus regex (fails on all real rulings); flagging in the next reviewer prompt (never puts back); a retry pass after the put-back (more code, no sighting shows a retry would land).
- **Trade-off accepted:** one model read per fix pass that carries a ruling.

### 6. Enforce a review of a /code resume diff
- **Choice:** `code/phase_start.py --resume` records the resume base (head and work-tree fingerprint) in start.json. The existing SubagentHandback hook entry (`review/handback_hook.py`) calls a new module `code/resume_review_gate.py` for the code-fork agent type: it denies the hand-back once when the tree differs from the resume base (notes paths left out, through `reviewed_tree` fingerprints) and no `code_review_start` run is newer than the resume. Fail-open with no start.json; fail-closed on a changed resume tree with no review run. The test drives `phase_start.py --resume`, a source edit and a captured code-fork SubagentHandback event.
- **Reasoning:** only a gate can stop the fork from closing the phase; the hook entry already runs on every hand-back, so no settings.json change is needed.
- **Alternatives rejected:** skill text only (the fork skipped skill text twice); a new settings.json hook (needs the user's yes for a settings change, and the entry exists).
- **Trade-off accepted:** a /code fork that resumes with a ruling-only change still gets denied when the tree moved; the deny text names the review start command.

### Q1. Cross-session rejected rows
- **Choice:** keep rejected rows per session. No sighting shows the re-filing run had another session id; the size rule sends that case to the fallback stop.
- **Reasoning:** the ticket names one lane session across all runs.
- **Alternatives rejected:** a store walk across sessions by repo (new code for an unseen case).
- **Trade-off accepted:** a relaunched session re-files once.

### G1. Item 6 gate point (revises D6)
- **Choice:** the gate runs on the code-fork's Write of `<run folder>/stop.md`, through the existing `gates/fork_write_scope.py` entry, not on SubagentHandback. `phase_start.py --resume` writes a new `resume.json` (repo, head, fingerprint, time, denied) owned by `code/resume_review_gate.py`; a plain start removes it; start.json is unchanged. The gate denies once when the tree differs from the resume base and no `loop-dir` file is in the run folder (phase_start moves `loop-dir` aside on every start, `phase_start.py:252`).
- **Reasoning:** only 107 of 512 real /code fork transcripts call SubagentHandback; every /code run ends with the stop.md Write, which fork_write_scope already gates for `code-fork`. A separate file leaves code_review_start's start-record grammar alone.
- **Alternatives rejected:** SubagentHandback only (misses about 79% of runs); a new SubagentStop hook (a settings.json change).
- **Trade-off accepted:** a fork that never writes stop.md, or never runs `phase_start.py --resume`, escapes the gate; the push gate's reviewed-tree check is the backstop.

### G2. Item 4 pass kinds
- **Choice:** four kind constants: `final read`, `class closure`, `prose repair`, `scoped re-review` (the late-repair read). The summary line prints only on cap-reached.
- **Reasoning:** the code has four post-round passes that advance the round count; the ticket names the late-repair read a scoped re-review.
- **Alternatives rejected:** a fifth `late repair read` kind (no pass of its own).
- **Trade-off accepted:** none in code.

### G3. Accepted asks on a cap-reached /code stop
- **Choice:** a session may rule the opened asks of a capped packet; an accepted one is recorded and applied by the resume, never by a coder before the stop.
- **Reasoning:** applying it after the cap lands unreviewed code.
- **Alternatives rejected:** apply in this run.
- **Trade-off accepted:** an accepted ask waits one resume.

### G4. Item 1 scope and cost
- **Choice:** the ruling check covers the rulings the run holds (header rulings and the pass's ruled findings), and runs once per fix pass in a run that holds any ruling. No store walk for rulings of earlier runs.
- **Reasoning:** the "reverted an earlier accepted rename" sighting needs every pass of a ruled run checked; the size rule and Q1 rule out a store walk.
- **Alternatives rejected:** check only passes on ruled findings (misses the rename revert); walk the store (unseen case).
- **Trade-off accepted:** one sonnet call per fix pass in a ruled run; a fresh run with no header rulings can still undo an earlier ruling.

Lane session ruling on G1-G4, agent-evals-c3-owner's go-ahead for steps inside this branch, 2026-11-23. None cuts or narrows an AC.

### Q2. Damage-path rulings on the criteria
- **Choice:** all nine as proposed: a ruling-check reply that fails to parse is a tool-fault stop and the pass stays; a file the backup could not save is named as not put back; the fresh-run gap (G4) is accepted and named by queue item in the final report; a relaunched lane re-files once; item 3's fix is the round label and immediate print if round-2 lines already print; a fork that skips `phase_start.py --resume` or the stop.md Write escapes, with the push gate as backstop; a ruling-only resume that moved the tree is denied once; a nameless live row cannot relay; unreadable lane files print `--by user` with a stderr note.
- **Reasoning:** each is the design's existing trade-off; none cuts an AC.
- Sign-off: agent-evals-c3-owner, 2026-11-23, owner `session`.

### G5-G14. Plan-review round 1 gaps
Report: `review-round1-shard-a.md`. None cuts or narrows an AC.
- **G5 packet plumbing:** Phase 4 and 6 also edit `review_loop_packet.packet_message` (writes `fix_rounds`, `post_cap_passes`, `against_ruling`) and `handback.read_header` (reads them). Tests assert on the packet read back through handback.
- **G6 old-packet default:** a packet without `fix_rounds` reads as None, and the cap line leaves the count out. External Contracts is fixed to match.
- **G7 relaunch:** `fix_rounds` and `post_cap_passes` are seeded from the prior header, the same way `iter_count` is (review_loop_main.py:157), with `fix_rounds` capped at ROUND_BUDGET.
- **G8 AC6 test:** the Phase 4 scenario also drives a late-repair read, and asserts `scoped re-review` in `post_cap_passes` and the stop text.
- **G9 Phase 5 reach:** the verification runs test_review_fix_script, test_waiting_review_launch, test_code_wait and test_reviewer_dispatch, and the phase updates the line shape in `_shared/review-fork-run.md:13`.
- **G10 fork text:** Phase 2 edits `_shared/review-fork-run.md:37`: in a `--by session` call, a user-only wanted-change ask may be `rejected`. Any other outcome stays `held`.
- **G11 AC14:** Phase 3 adds a test that `capped_review.effective_status` stays not clean after a session ruling on a capped packet. The `code/SKILL.md` Resume paragraph (:32) gets the step that applies an accepted capped ask through the fix launch.
- **G12 ruling-check failure:** catch `ReplyShapeError` and `ModelCallError`, and turn both into the tool-fault stop (Q2). Drop the outcome tags. Each ruling text goes to the model with its source key only.
- **G13 put-back scope:** back up the whole set of files `pass_scope` lets the pass write, not only `files_in_scope`.
- **G14 rule_instruction flag:** phase_asks computes the flag at both call sites (:175, :212). There is no default argument.
- Sign-off: agent-evals-c3-owner, 2026-11-24, owner `session`: all as proposed. Conditions: the G10 and G11 prose edits each get rule-meter on/off runs per ~/agent-evals/CLAUDE.md, or an `unmeasured` note in their change file. The code/SKILL.md hunk stays inside the Resume paragraph, and origin/master is merged before the push (fix/code-gates-nov23 also edits code/SKILL.md).

## Direction & Constraints

- `review_round` and `iter` keep their meaning: packet identity, ledger iter join, relaunch `--iter`.
- No new verb, route or state field in review_fix.py (999), review_fix_asks.py (978) or review_loop_script.py (973); new logic goes in new mixin modules.
- Hands off the mutation-tester, refactor and calibration files.
- Item 5's ticket premise holds only for a wanted-change ask (the loop already put the file back). For a revert ask, a session reject keeps the coder's CLAUDE.md edit; `tests/scripts/test_phase_asks.py:842` pins that refusal.
