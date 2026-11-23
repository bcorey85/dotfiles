# Decisions

## Phase 2: research

- 2026-11-22, lane code-skill-nov22 (session): the lane runs headless; the research summary and drill-down were not put to the user. The orchestrating session agent-evals-c3 receives the plan at hand-off. Research facts that bind the design:
  - The start-time hold (`code_review_start.py` `phase_held_files`) uses `phase_start.unchanged_dirty_files`, which drops a file whose bytes changed since `start.json` was written. The loop-time half (`review/review_loop_held.py`) already names a held file changed during a coder call as a tool fault (`HELD_FAULTS`); it belongs to the review-asks lane and is not edited here.
  - The review scope's changed set (`coder_gate.changed_files` less held paths) takes every untracked file in the work tree, whoever made it.
  - The code-fork agent's cancel rule is prose only (`agents/code-fork.md:14-15`); no script or hook tracks the fork's live children.
  - `review-fork-run.md` is read by /review and /fix only; /code holds its own copies of the waiting and reviewer text.

## Phase 3: scope

- Scope: backend (toolkit Python scripts under `claude/.claude/scripts/code/`, tests under `tests/scripts/`, and prose in `skills/code/SKILL.md` and `agents/code-fork.md`). Architect: backend-architect only.
- Depth: STANDARD. Three bounded phases (one per queue item), one layer, nothing destructive, no new dependency.

# Design Decisions — code-skill-1122

> Research: ./02-research.md
> Status: 8/8 resolved

## Queue

- [x] D1. Item 1 mechanism: how a cancel of a /code fork stops or names its live coder and its detached review loop — from backend-architect
- [x] D2. Item 2 hold signal: hold every path recorded in start.json for the whole phase, and name a byte change as a tool fault — from backend-architect
- [x] D3. Item 2 untracked attribution: which untracked files new since phase start enter the review scope — from backend-architect
- [x] D4. Item 3 cut set: what the /code skill trim removes, and how it reaches 10-15% — from backend-architect
- [x] Q1. Item 1: does the TaskStop hook wiring line go into settings.json through its owning lane, or does the item close on the in-bounds route? — from backend-architect
- [x] Q2. Item 2: a file dirty at phase start that the current phase also targets: held and named, or reviewed? — from backend-architect
- [x] Q3. Item 3: may /code's load change (Block B to a sibling file, read at phase end), and is the queued rank-1011 dedupe item folded into this plan? — from backend-architect
- [x] Q4. Item 1: was the 2026-11-22 cancel a main session that skipped the SendMessage-first route, or a fork that got `stop` and left its coder running? — from backend-architect

## Recommendations (sent to agent-evals-c3, 2026-11-22)

🔷 **D1. Item 1 mechanism**
- ➡ Rec: one reader in `scripts/code/fork_children.py`, composed from `open_child_gate.live_children` (imported, not copied) plus a scan of `subagents/*.meta.json` for `parentAgentId` = the fork id; an `interrupted` reading added to `lib/loop_transcript.py` (trailing `[Request interrupted by user]` record) so a TaskStopped child never reads as live. Two verbs: `fork_children.py <fork id>` prints the live child ids and SIGTERMs the run's detached review loop (`lib/process_group`, pid from `<run folder>/pid`); `fork_children.py hook` is a PreToolUse TaskStop hook that, on a code-fork task_id with live children, denies once per fork and names the ids. The hook script and its tests ship here; the one settings.json line goes to agent-evals-c3. SKILL.md:3 cancel route names the command.
- Other options: (A) PostToolUse TaskStop hook that only annotates the result (children named, not stopped, fork already dead); recording children in `code_wait.py agent` at dispatch (second owner of liveness, misses agents dispatched without a wait); coder_gate bash-hook deny after the fork is interrupted (stops Bash only; Write/Edit go on, which is the incident).
- Why: the harness registry already holds identity and liveness; a deny before the fork dies is the only route where nothing is written after the stop. ⚠ AC1's literal reading ("TaskStop's result names the live child id") is met only once the settings.json line lands; until then the in-bounds command meets it through the main session running it.

---

🔷 **D2. Item 2 hold signal**
- ➡ Rec: `phase_held_files` holds every path in `start.json`'s `dirty` map (not only same-bytes ones); `phase_start.unchanged_dirty_files` becomes `recorded_dirty_files` (callers: `code_review_start.py` and four test patches, no others); `code_review_start` adds a note per held file whose bytes differ from the record, worded like `review_loop_held.note_changed` ("by the coder or by the session that holds them"), carried in the prompt header and `review-scope.json` notes. Claim text drops "unchanged now". `handoff-block.md:28` and the two docstrings follow.
- Other options: keep the bytes check and add a second "was dirty" list (two signals, two owners); exempt paths the phase coder's transcript wrote (both writers possible on one file).
- Why: the bytes check is the bug. The loop's `HELD_FAULTS` already names a held file changed during a fix-coder call, so once the file is held the "tool fault" AC holds for the loop; the start-time note covers the phase-coder window the loop never sees.

---

🔷 **D3. Item 2 untracked attribution**
- ➡ Rec: with another live session in the repo, an untracked file absent from `start.json` and not written by this run's coders is held, with claim text naming it. "Written by this run's coders" = `file_path` of Write/Edit/NotebookEdit tool_use records in the transcripts of the coders the fork launched (ids from the fork transcript's Agent launches, via `loop_transcript`). A new reader of tool-use write paths goes in `lib/` only after `rg` confirms none exists (`loop_transcript.touches_plan(files_touched, …)` suggests one may). With no other live session: today's behaviour.
- Other options: handoff `files:`/WHY paths as attribution (`WHY: none` is allowed, so coder files vanish from review); a timestamp window (cannot tell sessions apart).
- Why: another session's file reaching the fix coder is the incident; a generator's output going unreviewed is named loudly and recoverable.

---

⚠ 🔷 **D4. Item 3 cut set**
- ➡ Rec: cut the in-load duplicates (SKILL.md:91/92 "do not mark the phase done", 6 words; the `:24` / code-fork.md:8-9 "coder makes every edit" overlap, 8 words, metered); meter and cut SKILL.md:34's restatement of global CLAUDE.md:26 (about 100 words); move Block B (:107-145, about 55 lines) to `skills/code/phase-end-block.md` read on the phase-end trigger (a template move, rules unchanged, no meter); update anchor rows 79-84. Leave every sentence shared only with `review-fork-run.md`: /code never loads that file, so those are not duplicates in the loaded text.
- Other options: (a) make /code read `review-fork-run.md` and cut the copies (pulls /review-only steps into /code); (b) a new `_shared` file for the waiting and reviewer text read by both (a load change for three skills, 88 exact words saved); (c) cut only the 14 in-load words and stop short of the 10-15% target.
- Why: ⚠ the ticket's premise ("exact duplicates, 150-250 words, safe") does not hold: measured, SKILL.md has 6 words of exact self-duplication and no exact cross-file duplicate inside the /code load. The 10-15% target is reachable only with the Block B move, which is the rank-1011 item's scope (Q3). Without Q3's yes, item 3 closes under its target and the change file says so.

---

❓ **Q1. settings.json line for the TaskStop hook**
- ➡ Rec: yes, hand the line to the settings.json owner (agent-evals-c3 or the gates lane); the script and tests ship on this branch either way. Needs answer from agent-evals-c3.

---

❓ **Q2. A held file the current phase also targets**
- ➡ Rec: held and named, not reviewed. Reviewing it means the fix coder can write a file another live session is editing; naming it costs one line the user reads. Not an AC cut: the AC says "stays held for the whole phase".

---

⚠ ❓ **Q3. Load change and the rank-1011 item**
- ➡ Rec: fold `code-skill-dedupe-the-stop-rule-and-move-the-phase` into this plan's item 3 phase (claim it from this lane) and allow the Block B sibling-file read. Scope is the queue owner's call. Needs answer from agent-evals-c3.

---

❓ **Q4. Nature of the 2026-11-22 cancel**
- needs answer from the user (transcript is on the work machine). D1 ships both routes, so the design does not wait on it; the answer decides whether the change file records a prose-compliance or a mechanism gap.

## Resolved

### 1. Item 1 mechanism (D1, Q1)

**Choice**: `scripts/code/fork_children.py` with two verbs. `<fork id>` prints the fork's live child ids and SIGTERMs the run's detached review loop. `hook` is a PreToolUse TaskStop hook, matcher TaskStop only, that denies a TaskStop of a code fork with live children, once per fork, naming the ids. Liveness comes from `open_child_gate.live_children` plus a `parentAgentId` meta scan, with an `interrupted` reading added to `lib/loop_transcript.py`. The hook's median time is measured next to a bare Python start; both go in the change file. The settings.json wiring line goes to agent-evals-c3 at branch end. The item closes on the command plus the hook.
**Reasoning**: agent-evals-c3, 2026-11-22, approved the recommendation and ruled the settings line the user's step. The 2026-11-22 cancel was the main session running TaskStop on the fork directly; TaskStop returned success and named no children, the coder kept running, rewrote a deleted file and handed back. The change file is worded on that route.
**Alternatives rejected**: PostToolUse annotation (the fork is dead before the children are named, so the coder still writes); recording children at `code_wait.py agent` (second liveness owner, misses agents dispatched without a wait, goes stale on cancel); coder_gate bash-hook deny (stops Bash only; the incident's Write goes through).
**Trade-off accepted**: until the settings line lands, the deny does not fire; the main session must run the command. A TaskStopped child reads as interrupted only through the transcript's trailing interrupt record.

### 2. Item 2 hold signal (D2, Q2)

**Choice**: every path in `start.json`'s `dirty` map is held for the whole phase. `unchanged_dirty_files` becomes `recorded_dirty_files`. `code_review_start` notes each held file whose bytes differ from the record as a fault, worded like `review_loop_held.note_changed`. A held file the current phase targets stays held and named, not reviewed.
**Reasoning**: agent-evals-c3, 2026-11-22, approved the recommendation. The bytes check is the bug; the loop's `HELD_FAULTS` covers fix-coder calls once the file is held, and the start-time note covers the phase-coder window.
**Alternatives rejected**: a second "was dirty" list beside the bytes check (two signals, and the fix coder still edits the dropped file); exempting paths the phase coder wrote (both writers possible on one file, so the other session's edit is overwritten unseen).
**Trade-off accepted**: the run's own edit of a start-dirty file goes unreviewed when another live session is present; it is named in the prompt header.

### 3. Item 2 untracked attribution (D3)

**Choice**: with another live session in the repo, an untracked file absent from `start.json` and not written by this run's coders (Write/Edit/NotebookEdit `file_path` in the launched coders' transcripts) is held, with claim text naming it. With no other live session, no change.
**Reasoning**: agent-evals-c3, 2026-11-22, approved the recommendation. Another session's file reaching the fix coder is the incident.
**Alternatives rejected**: handoff `files:`/WHY paths (`WHY: none` is allowed, so a real coder file would vanish from review); a timestamp window (cannot tell sessions apart, so the other session's file still enters scope).
**Trade-off accepted**: a file a coder-run generator wrote is held and named rather than reviewed.

### 4. Item 3 cut set (D4, Q3)

**Choice**: cut the in-load duplicates (SKILL.md:91/92, 6 words; the SKILL.md:24 / code-fork.md:8-9 overlap, 8 words, metered), meter and cut SKILL.md:34's restatement of global CLAUDE.md:26, and fold the rank-1011 item `code-skill-dedupe-the-stop-rule-and-move-the-phase` into this plan: one owner per stop rule, dense paragraphs to lists, Block B to a sibling file read on the phase-end trigger (structure change, no meter), anchor rows updated. Sentences shared only with `review-fork-run.md` stay. The trim item closes with the measured 14 words and the wrong premise in its outcome.
**Reasoning**: agent-evals-c3, 2026-11-22, approved the fold and ruled the template move needs no meter run; every reworded sentence still gets one.
**Alternatives rejected**: making /code read `review-fork-run.md` (pulls /review-only steps into every /code run); a new `_shared` file for the waiting and reviewer text (a load change for three skills to save 88 words); cutting only the 14 in-load words (misses the 10-15% target with nothing recorded).
**Trade-off accepted**: the Phase-Complete template is read from a second file at phase end, one more Read per phase end.

### 5. Nature of the 2026-11-22 cancel (Q4)

**Choice**: a mechanism gap on the direct-TaskStop route, not a prose-compliance gap.
**Reasoning**: agent-evals-c3, 2026-11-22: the main session ran TaskStop on the fork; TaskStop returned success and named no live children.
**Alternatives rejected**: none; this is a fact ruling, recorded so the change file's wording has a source.
**Trade-off accepted**: none.

## Direction & Constraints

- Out of bounds on this branch: `scripts/review/*`, `code/plan_check.py`, `gates/*`, `settings.json`, every CLAUDE.md, `orchestration.md`. Importing from `review/` is allowed.
- Liveness owner: `lib/loop_transcript.py` (`agent_finished`, `finished_by_meta`); child enumeration owner: `review/open_child_gate.py` `live_children`. No second copy.
- Corrected ticket premise (item 3): the exact-duplicate pool inside the /code load is about 14 words, not 150-250.
- Corrected research line (item 1): a reader of a fork's live children exists (`open_child_gate.live_children`), used only at the fork's own hand-back.
- Reopens the 2026-11-13 drop of `taskstop-on-a-code-fork-orphans-its-coder-child` ("no toolkit script is on that path"): true for the stop, false for detection.
- Text pins to keep green or update: `tests/scripts/test_guidance_rules.py` (:29-56, :84-92, :184-211), `tests/scripts/test_code_skill_text.py`, `tests/scripts/test_rule_anchors.py`.

### 6. Architect DESIGN GAPS (Phase 6)

**Choice**: (1) rule-meter scenarios for each reworded /code sentence are added to `~/agent-evals/bin/rule_meter_scenarios.json`, committed alone with `git -C ~/agent-evals commit -- bin/rule_meter_scenarios.json`, then pull_keep_index and push; stop if another session has the file dirty. (2) Item 1's first AC is pending the settings.json wiring, not met; the item stays running and agent-evals-c3 closes it after the user installs the line. (3) Rank-1011 bullet 4 is split to queue item `dedupe-the-acceptance-criteria-none-rule-across` (agent-evals aa1498f9), not cut on this branch. (4) `code_wait.py` prints the held-changed tool-fault line after the packet. (5) The whole `## Phase-Complete Block` section moves to `skills/code/phase-end-block.md`. (6) Untracked directories are expanded to files inside `code_review_start`. (7) The hook test fixture is built from a transcript TaskStop input until a captured event exists after wiring.
**Reasoning**: agent-evals-c3, 2026-11-22, ruled 1-3 and confirmed 4-7 as decided by this lane. All seven match the architect's own recommendations, so the architect plan stands without a revision round.
**Alternatives rejected**: cutting bullet 4 here (files outside /code, other anchors); reporting AC1 as met on the CLI plus cancel route alone (the deny does not fire without the line); note-only tool fault in the prompt (the fork may never read it).
**Trade-off accepted**: the trim item's meter counts depend on scenario files in a second repo; one more Read per phase end.

### 7. Rule-meter detectors for /code sentences

**Choice**: new detector scripts go under `~/agent-evals/bin/rule_meter_checks/` as new files, each with a unittest beside the existing check tests, committed with `bin/rule_meter_scenarios.json` in one agent-evals commit. `rule_meter.py` stays untouched. A detector reads the fork's output text only, never the repo state.
**Reasoning**: agent-evals-c3, 2026-11-22. No existing detector reads a /code fork's output.
**Alternatives rejected**: reusing the closest existing detector (reads the wrong signal); editing `rule_meter.py` (another lane's file).
**Trade-off accepted**: one more test file per detector in agent-evals.

### 8. Acceptance-criteria walk

**Choice**: AC1's pending note names the user as the installer of the settings.json line. AC15 reads "the text /code loads at start (SKILL.md plus the files it reads before phase end) is at least 10% shorter by word count, counting the template move from item 4; the change file records the before and after word counts". The seven damage-path defaults stand as the plan states them (coder-generated file held and named; missing coder transcripts hold every untracked file with a note; a deleted held file counts as changed; the hook is fail-open; one deny on a stale live reading; a stale or reused loop pid is not killed and reports `not_review_loop` with exit 0; a non-fork id exits 2). The AC17 note is the sign-off for bullet 4's split. The four GREEN regression guards stay.
**Reasoning**: agent-evals-c3, 2026-11-22, at the criteria walk.
**Alternatives rejected**: the ticket's "10-15% shorter" band (an upper bound serves nothing once the move is counted).
**Trade-off accepted**: none.

### 9. Plan review round 1 (3 BLOCKER, 8 GAP; report in `review-round1-shard-a.md`)

**Choice**: (a) `phase_start.py` records the holder session in start.json; `code_review_start.py` holds every recorded dirty path when start.json names a holder, whether or not that session is still live; a run with no holder at start is unchanged. (b) start.json records every session id that ran the phase (a resume appends its id); untracked attribution reads the coder transcripts of all of them; an untracked file no recorded coder wrote is held with a note that names it. A file the review loop's `claude -p` fix coder wrote stays held with that note; a queue item asks the review lane to record its coder's writes so a later round lifts that hold. AC9 is not reduced to a note. (c) AC2 is verified by the manual AC20 run only; the coverage table says so; the interrupted-reading unit test stays. (d) AC15's count runs on the four-file start load (SKILL.md 3033, `_shared/modifiers.md` 114, `_shared/plan-reading.md` 205, `_shared/handoff-block.md` 476; 3828 words, limit 3445); the change file records the four counts. The other eight findings (anchor rows re-hashed in the phase that edits the file; `print_held_fault` redesigned without the import cycle, the wrong folder and the exit; the tool-fault line written into `review_prompt` and tested on the detached prompt; dead folder-expansion code dropped; AC11 text and location named; checker scripts listed as Files; `verify-prep` added to the bounds list; one hold reading and one claim format; the earlier-phase rule kept in handoff-block.md) are plan repairs the architect writes.
**Reasoning**: agent-evals-c3, 2026-11-22, in answer to the three rulings asked.
**Alternatives rejected**: dropping the foreign-untracked hold to a note; a live-session gate for the whole phase; an automated AC2 replay test that holds by construction.
**Trade-off accepted**: a loop fix coder's new file is held with a note until the review lane records its writes.
**Addendum**: the architect's DESIGN GAP 1 (what "no recorded holder" means) reads as today's rule: same-bytes start-dirty files are held only while another session is live at review, with claim `dirty at the run start, unchanged now`; an old start.json with no holder key takes the same route. This is agent-evals-c3's "solo runs (no holder at start) unchanged", recorded as that ruling, 2026-11-22.

### 10. Phase 2 review asks (cap reached, round 5)

**Choice**: (1) `foreign_untracked` drops the paths this phase's plan section names (`expected_red.phase_own_paths`), so an untracked file a coder made through Bash (a change file, a copied fixture) is reviewed when the plan names it; AC13 holds. (2) An empty `sessions` list keeps the hold on every foreign untracked file, with the note naming the cause (`CLAUDE_CODE_SESSION_ID` was unset at phase start). (3) A recorded holder is honored whether or not `CLAUDE_CODE_SESSION_ID` is set at review; the own session id gates only the live-holder fallback route. (4) `check_record_base(repo, base_commit, record)` replaces the planned `recorded_dirty_files`; the Presence line follows. (5) handoff-block.md:28 parenthetical says "at a phase start or at review", since the no-holder fallback also holds. (6) The stale `review_loop_prompt_file.py:7-8` docstring is out of bounds: reported to agent-evals-c3 for the review lane, not edited here.
**Reasoning**: code-skill-nov22 lane, 2026-11-22, within agent-evals-c3's block 9 rulings (AC9 not reduced to a note; AC13 keeps own-coder files reviewed).
**Alternatives rejected**: skipping the hold on an empty `sessions` list (drops AC9 silently); attributing Bash-written files by parsing coder Bash commands (a second parser).
**Trade-off accepted**: an unplanned file a coder made through Bash is still held under a holder.

### 11. Rule-meter detector registration for the /code sentences

**Choice**: option (a). One registration-only dispatch entry in `~/agent-evals/bin/rule_meter.py` for a new `bin/rule_meter_code_skill.py`; detector bodies and tests stay in the new module. First check whether `rule_meter_fixture.DETECTORS` or `rule_meter_verifier.DETECTORS` already takes this kind of detector (the toolkit-scripts lane registers through `rule_meter_verifier.DETECTORS` with `rule_meter.py` untouched); if either fits, use it and leave `rule_meter.py` alone. `git -C ~/agent-evals status --short bin/` right before the edit; stop if any rule_meter file is dirty. The entry is committed with the scenarios file on bench-base in one commit, after `pull_keep_index.py`, then pushed. AC15 and AC21 stand as written.
**Reasoning**: agent-evals-c3, 2026-11-22, in answer to the lane's three options.
**Alternatives rejected**: shipping the cuts unmetered (AC21 fails); lowering the AC15 limit (AC15 changes).
**Trade-off accepted**: one line in another lane's file.

### 12. AC15 limit set to the measured start load (session ruling on a plan-written criterion)

**Choice**: option (a). AC15's limit becomes 3488 words, the measured start load. No skill text is trimmed to reach 3445.
**Reasoning**: orchestrating session agent-evals-c3 ruled, 2026-11-22, relayed by the code-skill-nov22 lane. The criterion was written by the plan, so a session ruling is recorded here. Rule-meter counts, complied/graded, on vs off (opus, n=1): CF01 2/3 vs 0/3, CF02 1/3 vs 0/3, CF03 0/2 vs 0/3, CF04 and CF06 no graded cells, CF05 1/3 vs 0/3, CF07 2/3 vs 1/3. In no scenario does the off arm beat the on arm, so the counts support no cut. Start-load words: SKILL.md 2673, `_shared/modifiers.md` 114, `_shared/plan-reading.md` 205, `_shared/handoff-block.md` 496, total 3488 against the old limit 3445, a 43-word gap; baseline 3828.
**Alternatives rejected**: trimming unmetered text to reach 3445; cutting metered lines the counts support keeping.
**Trade-off accepted**: the start load is 8.9% shorter than the 3828 baseline, not 10%. The plants for CF04 and CF06 are queued by agent-evals-c3.

**Addendum (orchestrating session ruling, 2026-11-22)**: the word meter (`tests/scripts/skill_word_band.py`) does not count a bare list marker (`-`, `*`, `+` or `<digits>.`) as a word, because the list conversion of two dense paragraphs added 13 markers that are not words. No SKILL.md text is trimmed. Recounted start load: SKILL.md 2647, `_shared/modifiers.md` 110, `_shared/plan-reading.md` 201, `_shared/handoff-block.md` 484, total 3442 against the limit 3488 (still 3488), 46 under it and 10.1% below the 3828 baseline (3828 was counted with the old rule).

### 13. AC15 duplicate clause narrowed and AC17 one-owner clause held (session ruling on plan-written criteria)

**Choice**: AC15's duplicate clause covers the 6 exact-duplicate words already cut (the second `do not mark the phase done`). SKILL.md:24 stays as a paraphrase of code-fork.md:8-9; its 8 words are not an exact duplicate. AC17's one-owner clause is held: no stop-rule dedupe is made in this phase.
**Reasoning**: orchestrating session agent-evals-c3 ruled, 2026-11-22, relayed by the code-skill-nov22 lane. The criteria were written by the plan, so a session ruling is recorded here. The rule-meter read for the stop-rule sentences is 2/3 vs 1/3 (CF07, n=1), which supports no cut.
**Alternatives rejected**: cutting SKILL.md:24 or the stop-rule sentence unmetered.
**Trade-off accepted**: one rule keeps two owners until a graded run supports a cut.

### 14. AC15 word-count clause reworded to the ruled limit (session ruling on a plan-written criterion)

**Choice**: AC15's "at least 10% shorter by word count" clause reads "under the ruled limit of 3488 words (03-decisions.md block 12)". The start load is 3461 words on the bare-marker counter (2647 / 110 / 201 / 503); the old base on that counter is 3769.
**Reasoning**: orchestrating session agent-evals-c3 ruled (Ask B, accepted), 2026-11-22, relayed by the code-skill-nov22 lane. The criterion was written by the plan, so a session ruling is recorded here. Block 12 already set the limit at 3488; the percent clause no longer matches it.
**Alternatives rejected**: trimming unmetered text to reach 10%.
**Trade-off accepted**: AC15 no longer states a percentage.

### 15. Follow-up: the later-phase holder in `kept_record` is not held (Ask A, rejected)

**Choice**: the code stays as it is. The later-phase holder at `claude/.claude/scripts/code/phase_start.py:189` (`kept_record`) is not held; this is outside the item's done clause. It is a follow-up, not a queue item of this branch.
**Reasoning**: orchestrating session agent-evals-c3 ruled (Ask A, rejected), 2026-11-22, relayed by the code-skill-nov22 lane. agent-evals-c3 queues the follow-up.
**Alternatives rejected**: changing `kept_record` in this phase.
**Trade-off accepted**: the gap stays open until agent-evals-c3's queued item lands.

### 16. `branch_bounds.py` is close-pass scaffolding, deleted before merge (branch review ask 1, accepted)

**Choice**: `tests/scripts/branch_bounds.py` and `tests/scripts/test_branch_bounds.py` are deleted before merge. The Phase 4 Bounds check ran once on this branch and passed: `python3 tests/scripts/branch_bounds.py 8436be97f25cd96ffa9f4ae8c72f37ff32173768 c7c330eec43626055bfeb4cb2474aa1ab9325e9b` exit 0 (pre-rebase hashes; the rebased diff touches the same paths). The plan's Phase 4 Files line stands as the record of what was built and then removed.
**Reasoning**: standing ruling by orchestrating session agent-evals-c3, 2026-11-22, relayed by the code-skill-nov22 lane. The checker hardcodes one lane's bounds; after merge it describes a closed lane and would run in every suite.
**Alternatives rejected**: keeping it as a general tool (no other lane has this bounds list).
**Trade-off accepted**: a later lane with its own bounds writes its own check.

### 17. The 3488 start-load limit is an AC15 close check, not a suite gate (branch review ask 2, accepted)

**Choice**: `tests/scripts/test_skill_word_band.py` is dropped. `tests/scripts/skill_word_band.py` stays as the AC15 close check; the Phase 3 change file names its 3461 reading against the 3488 limit.
**Reasoning**: standing ruling by orchestrating session agent-evals-c3, 2026-11-22, relayed by the code-skill-nov22 lane. `_shared/handoff-block.md` is shared with /review and /fix, so a permanent gate 27 words under the limit would fail a lane that never touched /code.
**Alternatives rejected**: keeping the suite test with a wider limit.
**Trade-off accepted**: a later growth of the /code start load is caught by a meter run, not by the suite.

### 18. A recorded-holder file the current coder edits stays flagged (branch review ask 3, rejected for this branch)

**Choice**: `recorded_holder_rows` keeps flagging a change to a held file from an earlier phase as a tool fault, even when the current coder's `coder_written_paths` holds that change. The release-of-own-write case is a follow-up queue item in `~/agent-evals`, filed by the code-skill-nov22 lane.
**Reasoning**: standing ruling by orchestrating session agent-evals-c3, 2026-11-22, relayed by the code-skill-nov22 lane; this is the same class as decision 15 (the later-phase holder) and is ruled out of this branch with it.
**Alternatives rejected**: dropping the changed file from the held rows when the current coder wrote it.
**Trade-off accepted**: a phase that edits an earlier phase's leftover is reported as a fault until the follow-up lands.
