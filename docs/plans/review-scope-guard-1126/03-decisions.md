# Decisions

Criteria owner: `session` (queue items written by a session). The orchestrating session, agent-evals-74, rules on any cut or reword.

## Settled in research (Phase 2, 2026-11-26, lane session; no user present, lane rule: phase end is no stop)

- D0.1 The root cause of ticket 1 (the resumed loop diffed against the origin/master tip) is already fixed on this base. `lib/merge_free_base.py` `resolve_base` swaps a base that is no ancestor of HEAD for its merge base. Both launchers use it: `review_launch.resolved_base` (the resume path) and `code_review_start.diff_base`. The loop reads the resolved base from the prompt header. No loop change is needed for the base.
- D0.2 The first half of ticket 1's Done-when (an out-of-diff edit is put back or named in the stop packet) is built: the scope guard puts the file back. The stray-file stop exists too. Tests at tests/scripts/test_review_loop_scope_guard.py:1173 (stray stop, `critical-blocker`) and :1209 (out-of-diff edit put back, named in `tool_fault`). This plan cites those tests as evidence and adds none for that half, unless Phase 4 finds a gap.
- D0.3 Open work: (a) a fix pass that changes text an AC quotes is filed as an ask and put back; (b) a fix pass that writes outside the reviewed repo's work tree ends in a blocker.

## Scope (Phase 3)

- Backend only (toolkit Python scripts). Depth STANDARD: two bounded pieces in one layer, nothing destructive, no new dependency. backend-architect runs.

# Design Decisions — review-scope-guard-1126

> Research: ./02-research.md
> Status: 15/15 resolved (lane session rules on design; ⚠ items sent to agent-evals-74)

## Queue

- [x] D1. Source of AC text — from backend-architect
- [x] D2. Which quoted spans count — from backend-architect
- [x] D3. Trigger and comparison — from backend-architect
- [x] D4. Remedy for an AC-quoted change — from backend-architect
- [x] D5. Where the AC guard lives — from backend-architect
- [x] D6. How coder_call gets the session id — from backend-architect
- [x] D7. Which outside paths block — from backend-architect
- [x] D8. How the outside write surfaces — from backend-architect
- [x] D9. Unreadable transcript — from backend-architect
- [x] D10. Coder-died path — from backend-architect
- [x] Q1. No plan on disk — from backend-architect
- [x] Q2. Where the incident's AC lived — from backend-architect
- [x] Q3. A finding that asks for the AC-text change — from backend-architect
- [x] Q4. Blocker or put-back for outside writes — from backend-architect
- [x] Q5. Bash writes outside the repo — from backend-architect

## Resolved

All blocks below: ruled by the lane session (fix/review-scope-guard-outside), 2026-11-26, on the architect's brief. No user present; the orchestrating session is agent-evals-74.

### D1. Source of AC text
- **Choice:** the plan's acceptance-criteria file (`criteria_by_id`) plus the ticket beside the plan (`ticket_criteria`), when a plan is on disk.
- **Reasoning:** both are where a ticket AC is written down; both already have one owner reader in plan_format.
- **Alternatives rejected:** criteria file only (misses an AC that lives only in the ticket, as in queue-item tickets); handoff free text (no grammar; guesses).
- **Trade-off accepted:** `ticket_criteria` reads only the first criteria section, so a two-ticket file contributes its first section only.

### D2. Which quoted spans count
- **Choice:** double and curly quoted spans, plus backtick spans that hold whitespace. One new owner function in `lib/plan_format.py` (`criterion_quotes`) built on `message_text.QUOTED_SPAN`.
- **Reasoning:** the incident's quote is prose ("Bash timeout up to 600000 ms"). 175 of 347 backtick spans on real AC lines are 12 characters or fewer (identifiers like `ts`) and would fire on every rename.
- **Alternatives rejected:** all spans (false put-backs of identifier renames each round); length floor (arbitrary, still hits long identifiers).
- **Trade-off accepted:** a single-word backticked AC value (a flag name) is not guarded.

### D3. Trigger
- **Choice:** a quoted span present in a pass-scoped file before the pass and absent from that file after it; raw text match. Files: the pass's scope files outside the plan folder, as `snapshot_comments` takes them.
- **Reasoning:** absence is what changed the meaning in the incident; out-of-scope files are already put back by the scope guard.
- **Alternatives rejected:** count drop (fires on a legitimate de-dup).
- **Trade-off accepted:** a span split across lines or string concatenation is not seen.

### D4. Remedy
- **Choice:** put back only the lines that held the span (`put_back_lines`), keep the pass's other edits, and file one ask per span naming the AC id, the file and the span. An accepted ask (PLACE_MARKER text in the pass's findings) exempts it; a rejected question keeps the put-back and files no new ask.
- **Reasoning:** ticket 1 says "filed as an ask, not applied"; line-level put-back keeps the other fixes in the same file.
- **Alternatives rejected:** PLAN-IMPACT route (applies nothing back; the edit ships); ask without put-back (the change stays applied); whole-file revert (undoes unrelated fixes).
- **Trade-off accepted:** one extra ask round when a fix legitimately rewords quoted text.

### D5. Where the AC guard lives
- **Choice:** a new mixin module `review/review_loop_criteria_quotes.py`, called from `undo_protected_edits`; the `(signoffs, comments)` tuple becomes a NamedTuple of three snapshots so `failed_pass_blocker` unpacks by name. Owner line added to `claude/.claude/scripts/CLAUDE.md` (owner-line exception).
- **Reasoning:** review_loop_script.py is at 971 lines; the guard pattern lives in mixins.
- **Alternatives rejected:** inline in `repair` (breaks the 1000-line rule).
- **Trade-off accepted:** one more module.

### D6. Session id reach
- **Choice:** `claude_call_reply(...)` returns a NamedTuple `(text, session)`; `claude_call` delegates to it and returns text; `coder_call` uses the reply form.
- **Reasoning:** reads a field, no output parsing; other callers unchanged.
- **Alternatives rejected:** change all 4 callers (wide diff); read `CALLS[-1]` (racy, parses logged output).
- **Trade-off accepted:** two entry points to one call.

### D7. Which outside paths block
- **Choice:** any Write/Edit/MultiEdit/NotebookEdit path that resolves outside the resolved repo root blocks, except paths under the temp dir (`tempfile.gettempdir()` and `/tmp`) and the loop's out dir. Both sides resolved, so `~/.claude` → `~/dotfiles` is caught.
- **Reasoning:** the ticket's Done-when names any file outside the reviewed repo's work tree; narrowing to "inside another git repo" would narrow the AC. coder-core sanctions only `/tmp` scratch.
- **Alternatives rejected:** only other git work trees (narrows the AC; leaks `$HOME` dotfiles writes).
- **Trade-off accepted:** a coder scratch file in `~/scratch` stops the loop (1 case in 394 sampled calls).

### D8. Surface
- **Choice:** `coder_call` records the outside paths; `repair` raises `OutsideWriteError` right after `stop_on_stray_files` (after `files_touched.update`), and `review_loop_main.py` catches it as `critical-blocker` naming each path and saying the loop did not put it back.
- **Reasoning:** matches the stray-file stop; the run does not end as converged.
- **Alternatives rejected:** `CoderCallError` (turns a finished pass into a died-pass record).
- **Trade-off accepted:** none beyond one error type.

### D9. Unreadable transcript
- **Choice:** fail open with a `tool_fault` note naming the session id and the projects folder. The test fake gains a `transcript_writes` reply key that writes a transcript.
- **Reasoning:** every existing harness call has no transcript; a missing transcript is a tool fault, not evidence of an outside write.
- **Alternatives rejected:** fail closed (stops every run whose transcript is late or under another config dir).
- **Trade-off accepted:** a run with an unreadable transcript is unchecked, said in the packet.

### D10. Coder-died path
- **Choice:** not covered; the died-pass blocker already stops the run.
- **Reasoning:** no session hit it (size rule).
- **Alternatives rejected:** scanning in `failed_pass_blocker` (code for an unseen case).
- **Trade-off accepted:** a died pass's outside write is not named.

### Q1. No plan on disk
- **Choice:** the AC guard is off and files no note.
- **Reasoning:** with no plan there are no ACs the loop can read; a plain /review has no contract to protect.
- **Alternatives rejected:** read the brief text (no grammar).
- **Trade-off accepted:** ⚠ sent to agent-evals-74: if the incident ran without a plan, this guard would not have caught it.

### Q2. Incident AC location
- **Choice:** not found on this machine; D2 covers both quote forms, so the design does not depend on it.
- **Reasoning:** the quote holds whitespace, so either form is guarded.
- **Alternatives rejected:** none.
- **Trade-off accepted:** none.

### Q3. A finding that asks for the change
- **Choice:** still an ask (literal Done-when), unless an accepted ask already rules it.
- **Reasoning:** the reviewer is not the AC owner.
- **Alternatives rejected:** treat the finding as the request (exactly the incident's failure).
- **Trade-off accepted:** one ask round.

### Q4. Blocker or put-back
- **Choice:** blocker only; no put-back in another work tree.
- **Reasoning:** no pre-pass snapshot exists there; a restore could destroy another session's edits. Done-when accepts either.
- **Alternatives rejected:** put back via git restore (destroys others' work).
- **Trade-off accepted:** the caller reverts the outside edit by hand.

### Q5. Bash writes outside the repo
- **Choice:** not covered; the blocker covers Write/Edit/MultiEdit/NotebookEdit calls.
- **Reasoning:** both incidents used Edit/Write; a Bash-write layer needs a hook in settings.json, outside this lane.
- **Alternatives rejected:** a PreToolUse hook (settings.json edit; per-call cost).
- **Trade-off accepted:** ⚠ sent to agent-evals-74: `sed -i` or a redirect outside the repo stays unseen.

## Direction & Constraints

- D0.1 correction (architect): only `code_review_start.diff_base` folds merged-in commits; `review_launch.resolved_base` calls `resolve_base` only. The incident's cause (non-ancestor base) is fixed on both paths; an ancestor base older than a merged-in master still diffs master's changes on the review_launch path. Out of this lane; reported to agent-evals-74.
- No new hook, no settings.json or CLAUDE.md edit beyond an owner line in scripts/CLAUDE.md.
- Counter-priming: PreToolUse write gate (settings.json, Bash leak); snapshot sibling repos (blames other sessions); whole-file put-back (undoes other fixes).

## Sign-offs

- Q1 ruled by agent-evals-74 (orchestrating session), 2026-11-26: accept the default. The guard runs only with a plan on disk; the change file says so.
- Q5 ruled by agent-evals-74 (orchestrating session), 2026-11-26: accept the tool-call scope. Read writes only through `lib/loop_transcript.py` `written_paths`, with no second transcript scan. `written_paths` reads Write/Edit/MultiEdit/NotebookEdit only and no Bash redirect targets, so Bash writes stay out; the change file's Result names that gap. No settings.json edit.
- D0.1 correction (review_launch has no merged-in fold): agent-evals-74 queues it; out of this lane.
- Damage-path rulings by agent-evals-74 (orchestrating session), 2026-11-26:
  - D7/G1 accepted: temp-dir and out-dir writes are exempt; a temp root that holds the repo is not.
  - D9 accepted, amended: the unreadable-transcript note shows in the stop packet's `tool_fault`, not only in a log.
  - D2/D3 accepted: one-word backticked values and spans split across lines are not guarded.
  - Malformed criteria source changed (G4): a malformed criteria file does not stop the loop; the AC guard is off for the run and a `tool_fault` note names the file. /verify owns criteria-file health.
  - D10 changed: a died pass's transcript is scanned through the same path as a finished pass, and its outside writes are named in its blocker; the D9 note applies only when the transcript cannot be read.

## Design gaps from the architect's plan (lane session, 2026-11-26)

### G1. Temp root that holds the repo
- **Choice:** a temp root that holds the reviewed repo is not a scratch root; the out dir always is.
- **Reasoning:** otherwise a repo under /tmp (the test harness, a /tmp clone) can never be guarded, and Ticket 2's test cannot run.
- **Alternatives rejected:** always allow temp (untestable; sibling /tmp repos unguarded); env knob (test-only knob).
- **Trade-off accepted:** a coder in a /tmp repo that writes a /tmp helper stops the loop.

### G2. Test mocks of claude_call
- **Choice:** re-point the 12 in-process mocks to `claude_call_reply`.
- **Reasoning:** keeps D6; the review-loop test run catches a missed one.
- **Alternatives rejected:** keep coder_call on claude_call (re-opens D6).
- **Trade-off accepted:** a wider test diff.

### R1. Plan review round 1 (lane session, 2026-11-26; review-round1-shard-a.md)
- **Choice:** the BLOCKER (put-back picks the most similar line) goes back to the architect for a `may_replace` rule that keeps the pass's other fixes. GAP 1: record outside writes right after `claude_call_reply` returns, so the undo-failed path names them. GAP 2: Phase 0 gives the test an empty AC snapshot shape that Phase 1's undo reads without error. GAP 3: add `plan_ac_quotes` to `RealPlansTest`. GAP 4: add loop-level tests for AC6, AC7 and AC9. GAP 5: the error names the file it came from. NITs fixed in the same text, except the incident-quote one (Q2 already covers it).
- **Reasoning:** each is a plan defect, not a scope change; no AC moves.
- **Alternatives rejected:** state AC6/AC7/AC9 as unit-only exceptions (the plan's own rule says no).
- **Trade-off accepted:** more loop-level tests, slower Phase 1 and 2 runs.

### G3. Ticket with no criteria heading
- **Choice:** adds no quotes; the loop goes on.
- **Reasoning:** no criteria means nothing to guard; stopping would break reviews of plans whose ticket has no heading. A malformed criteria section still stops.
- **Alternatives rejected:** stop the loop (breaks unrelated reviews).
- **Trade-off accepted:** an AC under a non-standard heading is not guarded.

### Q6. Third queue item: the guard put back a move target
- **Asked by:** agent-evals-74, 2026-11-26: cover `review-loop-scope-guard-reverts-a-file-that-a` in this branch if the base does not.
- **Choice:** the base already meets its Done-when; no code change. A file a finding names stays changed (test_review_loop_scope_guard.py:387, :408). An unnamed file the gate needs stays (:829, :1204 at the loop level). Any other put-back file stops the loop with a stop naming it (:839, :847, :862, :1179, :1196). The scope guard's gate judging landed in 769426995 and d166edb14 (2026-11-25 22:28 and 2026-11-26 01:36); which code the incident ran is unknown.
- **Evidence:** Phase 1's own review loop hit the same put-back (helpers moved into `lib/script_utils.py`). It ran the stowed `~/dotfiles` master, which lacks d166edb14.
