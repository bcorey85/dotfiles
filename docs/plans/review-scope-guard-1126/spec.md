# Review loop fix pass: text an AC quotes, and writes outside the reviewed repo

> Ticket: ./00-ticket.md (two session-written queue items)
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-26

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

The review loop's fix pass gets two more guards. First, when a pass removes text that an acceptance criterion quotes from a file under review, the loop puts back the lines that held it, keeps the pass's other edits, and files one ask that names the criterion, the file and the text. Second, when a coder call writes a file outside the reviewed repo's work tree (read from the coder's own transcript), the loop stops with a `critical-blocker` that names each path and says it was not put back. Ticket 1's first half (an out-of-diff edit is put back) and its root cause (a non-ancestor base) are already fixed on this base (D0.1, D0.2).

## Phase Status

- [ ] Phase 0: Contracts — PassSnapshots, CallReply and claude_call_reply, with no behaviour change (risk: high)
- [ ] Phase 1: Walking skeleton — the AC-quote guard, end to end (risk: low)
- [ ] Phase 2: The outside-write guard (risk: low)
- [ ] Phase 3: Owner lines and the full suite (risk: low)
- [ ] Phase 4: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

## Decisions

- D0.1 Base root cause — already fixed by `resolve_base` on both launch paths; no loop change.
- D0.2 Out-of-diff edit — already put back by the scope guard; the two tests named in Phase 3 are its evidence.
- D1. AC source — the plan's `acceptance-criteria.md` (`criteria_by_id`) plus the ticket beside the plan (`ticket_criteria`, first criteria section only).
- D2. Quoted spans — double and curly quoted spans, plus backtick spans that hold whitespace, through `message_text.QUOTED_SPAN`. Trade-off: a one-word backticked value is not guarded.
- D3. Trigger — a span in a scoped file before the pass and absent from that file after it; raw substring test.
- D4. Remedy — put back only the lines that held the span (`whole_stretch=False`), one ask per (file, span); an accepted ask exempts it; a rejected one keeps the put-back and files no ask.
- D5. Placement — new mixin `review/review_loop_criteria_quotes.py`; `(signoffs, comments)` becomes `PassSnapshots`.
- D6. Session id — `claude_call_reply` returns `CallReply(text, session)`; `claude_call` delegates.
- D7. Outside path — any written path that resolves outside the resolved repo root, except scratch roots (temp dir, `/tmp`, the loop out dir).
- D8. Surface — `OutsideWriteError` raised after `stop_on_stray_files`, caught as `critical-blocker`; no put-back.
- D9. Unreadable transcript — fail open with a `tool_fault` note naming the session and the projects folder; the note is in the stop packet's `tool_fault` (ruled by agent-evals-74, 2026-11-26).
- D10. Died pass — scan its transcript through the same path as a finished pass; fail open with the D9 note only when it cannot be read (ruled by agent-evals-74, 2026-11-26).
- Q1. No plan on disk — the AC guard is off (ruled by agent-evals-74, 2026-11-26).
- Q3. A finding that asks for the change — still an ask.
- Q4. Outside write — blocker only.
- Q5. Bash writes — not covered; writes read only through `loop_transcript.written_paths` (ruled by agent-evals-74, 2026-11-26).
- G1. A temp root that holds the repo is no scratch root. Trade-off: a /tmp repo's /tmp helper script stops the loop.
- G2. The 12 in-process mocks of `review_loop_coder.claude_call` move to `claude_call_reply`.
- G3. A ticket with no criteria heading adds no quotes.
- G4. A malformed criteria file or ticket turns the AC guard off for the run, with a `tool_fault` note naming the file; the loop goes on (ruled by agent-evals-74, 2026-11-26).
- R1-B. AC put-back placement: `restore_protected_lines(..., in_place=True)`. A lost line of an equal-length rewrite goes back at its own offset; in any other rewrite the guard passes a `may_replace` that accepts no line, so the lost line is inserted and no line the pass wrote is overwritten. Trade-off: in an uneven rewrite, the reworded line stays beside the restored one until the ask is ruled.

## Approaches Considered and Not Taken

- A PreToolUse write gate for loop coders: needs a `settings.json` hook (outside this lane), misses Bash writes, and is no scope-guard blocker.
- Snapshot `git status` of sibling repos before and after each pass: blames the coder for other sessions' edits, and needs a guessed list of repos.
- Put back the whole file when an AC-quoted span vanishes: undoes the pass's other fixes in that file, which was the incident's main file.

## Constraints

- Python 3.10, no new dependency, snake_case, `bash tests/lint.sh` with its complexity gate (docs/toolkit-script-rules.md).
- `claude/.claude/scripts/review/review_loop_script.py` is 971 lines; it stays under 1000 (`exercised`: `wc -l`).
- Every Write/Edit `file_path` in 394 sampled coder transcripts was absolute; each tool_use appears twice (assistant record and `api-request-blob`); `script_utils.tool_use_calls` skips the blob copy (`exercised`, architect survey).
- `~/.claude` is a symlink to `~/dotfiles/claude/.claude`; only a resolved path shows a worktree coder's `~/.claude/...` edit lands in the main checkout (`exercised`).
- The loop out dir is under the git dir: inside the repo root for a main checkout, outside it for a worktree (`exercised`, review_loop_main.py:276).
- One owner per fact (claude/.claude/scripts/CLAUDE.md): no new quote regex, no second transcript scan, no parse of `calls.jsonl` or `call-NN-*.json`.
- A guard states fail-open or fail-closed in a comment; no swallowed exception.
- No settings.json, no CLAUDE.md edit beyond owner lines in `claude/.claude/scripts/CLAUDE.md`.

## External Contracts

- `claude -p --output-format json` reply holds `session_id`; the transcript lands at `<projects_dir>/<project>/<session_id>.jsonl` once the process exits (`exercised`: 394 of 394 sampled calls found). Broken if missing: D9 fail-open note, the run goes on unchecked.
- Transcript tool_use records carry `name` and `input.file_path` / `input.notebook_path` (`exercised`). Read only through `loop_transcript.written_paths`.

## Approach

- AC guard (piece a): snapshot each in-scope file that holds a quoted span before the pass; after it, put back the lines whose span vanished and file asks. Pattern: `review_loop_comment_removal.py` (snapshot, `undo_*`, ask filing), `review_loop_put_back.put_back_lines`.
- Outside-write guard (piece b): `coder_call` reads its own transcript after a successful pass; `repair` raises after the stray-file check. Pattern: `review_loop_stray_files.stop_on_stray_files`, the FAULTS lists read by `coder_fault_notes`.
- Ask text (one per file and span): `parse_finding(f"{AC_QUOTE_ASK_NOTE}. {labels} quote {quoted!r}; the pass removed it from {path}. Change: {change}")`, with `path` and `line` set to the first restored line; `quoted = inert_change_marks(one_line(span, None))`; `change = f"let the fix remove the text {labels} quote, {quoted!r}, from {path}"`; `labels` joined with `", "` so `phase_asks.hold_criterion_asks` sees `AC<n>`.
- Blocker text: `"{call_name} wrote files outside the reviewed repo {repo}: {paths}; the loop did not put them back, so revert them by hand before you push"`.
- Notes: unreadable transcript `f"{role}: the outside-write check could not run: no readable transcript for session {session!r} under {projects_dir()}"`; writes found `f"{role} wrote outside the reviewed repo (not put back): {', '.join(paths)}"`, written when found so `tool_fault` names them even when an earlier blocker fires first.

## Dependencies

- No external package.
- Internal: `lib/plan_format.py` (`criteria_by_id`, `ticket_criteria`, `ticket_beside`, `CRITERIA_FILE_NAME`, `NoCriteriaHeadingError`, `outside_plan_folder`), `lib/message_text.py` `QUOTED_SPAN`, `review/review_loop_put_back.py`, `review/review_loop_ruled.py` `plan_path_on_disk`, `review/review_loop_findings.py` (`inert_change_marks`, `REJECTED_ASK_REASON`), `lib/loop_transcript.py` `written_paths`, `lib/session_registry.py` (`session_transcript`, `projects_dir`), `lib/script_utils.py` (`repo_relative`, `one_line`).

## Implementation Plan

### Current State Analysis

The scope guard puts back out-of-scope files inside the repo and stops on strays. Nothing compares code text with AC text. `claude_call` drops the child's `session_id`, and no guard looks outside the repo root.

### Desired End State

A pass that removes AC-quoted text has those lines put back and an ask filed. A pass that writes outside the reviewed repo ends the run in `critical-blocker` naming the paths. Size estimate: about 365 production lines and 645 test lines (1010 total); the coder stops and reports if the diff passes 2020.

### What We're NOT Doing

- Writes outside the repo made through Bash (`sed -i`, redirects, helper scripts) — Q5.
- AC text from the brief when no plan is on disk — Q1.
- Ticket criteria sections after the first — D1.
- The `review_launch.resolved_base` merged-in fold — queued by agent-evals-74.
- New tests for ticket 1's first half — D0.2.

### Acceptance Criteria

- **Criteria file**: `docs/plans/review-scope-guard-1126/acceptance-criteria.md`

A test covers a criterion by its behavior, never by a marker: it asserts at the public boundary a user or caller reaches, never an internal function. **No mocks inside such a test.**

## Phase 0: Contracts

### Overview

The shared shapes both guards build on, with no behaviour change. Frozen at approval.

### Changes Required:

#### 1. Pass snapshots

**File**: `claude/.claude/scripts/review/review_loop_criteria_quotes.py` (new)
**Changes**: `class AcQuoteSnapshot(typing.NamedTuple)` with `texts: dict` ({path: text}) and `spans: dict` ({path: {span: [labels]}}), plus `EMPTY_AC_QUOTES = AcQuoteSnapshot({}, {})`. Nothing else yet.

**File**: `claude/.claude/scripts/review/review_loop_put_back.py`
**Changes**: add `class PassSnapshots(typing.NamedTuple)` with fields `signoffs`, `comments`, `ac_quotes` (an `AcQuoteSnapshot`, never None).

**Files**: `claude/.claude/scripts/review/review_loop_script.py`, `claude/.claude/scripts/review/review_loop_partial_fix.py`, `claude/.claude/scripts/review/review_loop_comment_removal.py`
**Changes**:
- `repair` builds `PassSnapshots(signoffs, comments, review_loop_criteria_quotes.EMPTY_AC_QUOTES)` after `snapshot_comments` and passes it to `failed_pass_blocker` and to `undo_protected_edits(snapshots, findings)`.
- `failed_pass_blocker` (review_loop_partial_fix.py:213-218) reads it by field, with no tuple unpacking.
- `undo_protected_edits` takes `PassSnapshots` and reads `snapshots.signoffs` and `snapshots.comments`.

#### 2. Call reply

**File**: `claude/.claude/scripts/review/review_loop_calls.py`
**Changes**: add `class CallReply(typing.NamedTuple): text: str; session: str` and `claude_call_reply(...)` with `claude_call`'s parameters, holding its current body and returning `CallReply(text, session)` (`session` is `""` when the reply had none). `claude_call` returns `claude_call_reply(...).text`. Its other callers stay.

**File**: `claude/.claude/scripts/review/review_loop_coder.py`
**Changes**: `coder_call` calls `claude_call_reply` and uses `reply.text`.

#### 3. Tests

**Files**: `tests/scripts/test_review_loop_coder.py`, `tests/scripts/test_review_loop_scope_guard.py`, `tests/scripts/test_review_loop_script.py`
**Changes**:
- The 12 in-process mocks of `review_loop_coder.claude_call` move to `claude_call_reply` and return `review_loop_calls.CallReply(text, "")`: test_review_loop_scope_guard.py:455, :470, :501, :526, :654, :672, :683, :695 (`ScopeGuardTest`), test_review_loop_coder.py:89, :110 (`UntrackedDeletionTest`), test_review_loop_script.py:3532, :3571 (`ReviewLoopScriptTest`).
- test_review_loop_coder.py:627 builds `review_loop_put_back.PassSnapshots(signoffs, comments, review_loop_criteria_quotes.EMPTY_AC_QUOTES)`; Phase 1's `undo_ac_quote_pass` reads that empty snapshot and returns `[]`.
- Add `test_claude_call_reply_returns_the_session_id` to `tests/scripts/test_review_loop_coder.py` (a fake `claude` on PATH prints a reply with `session_id`).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the reply carries the child's session id and every review-loop test still passes — `rg -q 'def test_claude_call_reply_returns_the_session_id' tests/scripts/test_review_loop_coder.py && python3 tests/parallel_tests.py test_review_loop_coder.py test_review_loop_scope_guard.py test_review_loop_script.py`
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/review/review_loop_put_back.py claude/.claude/scripts/review/review_loop_criteria_quotes.py claude/.claude/scripts/review/review_loop_calls.py claude/.claude/scripts/review/review_loop_coder.py claude/.claude/scripts/review/review_loop_script.py claude/.claude/scripts/review/review_loop_partial_fix.py claude/.claude/scripts/review/review_loop_comment_removal.py`

#### Manual Verification:

N/A (no behaviour change; the tests above cover it).

---

## Phase 1: Walking skeleton — the AC-quote guard

### Overview

A fix pass that removes text an AC quotes from a file under review has those lines put back, keeps its other edits, and files one ask naming the criterion, the file and the text.

### Changes Required:

#### 1. The span reader

**File**: `claude/.claude/scripts/lib/plan_format.py`
**Changes**: beside `criteria_by_id`, add:
- `ac_quotes(text) -> list[str]`: the inner text of each `message_text.QUOTED_SPAN` match, in order, de-duplicated; a backtick span counts only when its inner text holds whitespace; empty or whitespace-only spans are skipped.
- `plan_ac_quotes(plan_path) -> dict[str, list[str]]`: span → the labels that quote it.
  - `AC<n>` labels come from `plan_path.parent / CRITERIA_FILE_NAME` through `criteria_by_id(text, name=str(criteria_path))`.
  - `Ticket #n` labels come from `ticket_beside(plan_path)` through `ticket_criteria(text, name=str(ticket_path))`.
  - The full path as `name` makes every `PlanFormatError` message start with `<file path>:<line>:`.
  - A missing file adds nothing; `NoCriteriaHeadingError` adds nothing (G3); any other `PlanFormatError` propagates with its path prefix, and an `OSError` propagates naming its filename.

**File**: `claude/.claude/scripts/lib/protected_lines.py`
**Changes**: `restore_protected_lines` gains a keyword `in_place=False`. When it is True and a `replace` opcode has equal before and after lengths, each lost index `i` sets `stretch[i - before_start] = before_lines[i]` and keeps the stretch; every other opcode is handled as today, `may_replace` included. The equal-length branch lives in a helper `in_place_stretch` so `restore_protected_lines` stays under the complexity gate. Update the docstring. `in_place=False` output is byte-identical to today's.

**File**: `claude/.claude/scripts/review/review_loop_put_back.py`
**Changes**: `put_back_lines` gains `in_place=False` and passes it through.

#### 2. The guard

**File**: `claude/.claude/scripts/review/review_loop_criteria_quotes.py` (fills the Phase 0 module)
**Changes**: add `AC_QUOTE_ASK_NOTE`, `AC_QUOTE_FAULTS: list[str]`, `NEVER_REPLACE` (a def returning False), and the mixin `AcQuoteRuns`:
- `ac_quote_snapshot(files_in_scope, findings)`:
  - Returns `EMPTY_AC_QUOTES` when `self.plan_path_on_disk()` is None (Q1).
  - Reads `plan_format.outside_plan_folder(files_in_scope, self.plan)` minus held files.
  - On `PlanFormatError` or `OSError` it builds `f"the AC-quote guard is off for this run: {error}"` (the error text starts with the failing file's path; G4), appends it to `AC_QUOTE_FAULTS` only when not already there, and returns `EMPTY_AC_QUOTES`. Fail-open, stated in a comment.
- `undo_ac_quote_pass(snapshot, findings, skip=())`, per path in `snapshot.texts`:
  - Skip a path in `skip`, or one that no longer exists.
  - Lost spans are those in the snapshot text and not in the current text; drop a span whose `change` text is in the joined finding text (an accepted ask).
  - With spans lost, call `put_back_lines(repo, path, before, current, numbers, whole_stretch=False, may_replace=NEVER_REPLACE, in_place=True)` on the sorted before-text line numbers holding a lost span (R1-B), then `file_put_back_ask` once per span with `line=` its first number.
  - Return the `ProtectedPutBack` list; `EMPTY_AC_QUOTES` gives `[]`.

**File**: `claude/.claude/scripts/review/review_loop_ruled.py`
**Changes**: add `RuledFindings.file_put_back_ask(ask)`, moved from review_loop_comment_removal.py:228-234: skip an ask whose `ask_question` is already filed; `drop_asks([ask], REJECTED_ASK_REASON)` when its question is in `self.rejected_questions`; else `add_ask(CODER_GATE, ask)`.

**File**: `claude/.claude/scripts/review/review_loop_comment_removal.py`
**Changes**: `file_block_asks` calls `file_put_back_ask`; delete `rejected_block`; `undo_protected_edits` appends `self.undo_ac_quote_pass(snapshots.ac_quotes, findings, held)` after the comment put-back.

**File**: `claude/.claude/scripts/review/review_loop_coder.py`
**Changes**: add `review_loop_criteria_quotes.AC_QUOTE_FAULTS` to `coder_fault_notes`.

**File**: `claude/.claude/scripts/review/review_loop_script.py`
**Changes**: add `AcQuoteRuns` to the `LoopRun` bases; in `repair`, right after `snapshot_signoffs`, `quotes = self.ac_quote_snapshot(files_in_scope, findings)`, and build `PassSnapshots(signoffs, comments, quotes)`.

#### 3. Tests

**File**: `tests/scripts/test_protected_lines.py`
**Changes**:
- `test_in_place_puts_a_lost_line_back_at_its_own_offset_in_an_even_rewrite`: `limit = 1..5` rewritten to `limit = 1\nlimit = 20\nlimit = three\nlimit = 4\nlimit = 6\n` with line 3 protected gives `limit = 1\nlimit = 20\nlimit = 3\nlimit = 4\nlimit = 6\n`; `a = 1\n# set the Bash timeout up to 600000 ms\nb = 2\n` rewritten to `a = 10\n# about 150 seconds\nb = 2\n` with line 2 protected gives `a = 10\n# set the Bash timeout up to 600000 ms\nb = 2\n`.
- `test_in_place_with_never_replace_keeps_every_line_of_an_uneven_rewrite`: the `limit` case with `extra = 9` added after `limit = three` gives `limit = 1\nlimit = 3\nlimit = 20\nlimit = three\nextra = 9\nlimit = 4\nlimit = 6\n`.
- `test_in_place_false_is_unchanged`: the `limit` case with no new keyword gives today's `limit = 1\nlimit = 3\nlimit = three\nlimit = 4\nlimit = 6\n`.

**File**: `tests/scripts/test_plan_format.py`
**Changes**: `test_ac_quotes_takes_double_and_curly_quotes_and_spaced_backticks`, `test_plan_ac_quotes_reads_the_criteria_file_and_the_ticket_beside_the_plan`, `test_plan_ac_quotes_with_no_criteria_file_and_no_ticket_is_empty`, `test_plan_ac_quotes_ticket_with_no_criteria_heading_adds_nothing`, `test_plan_ac_quotes_duplicate_ac_id_raises_an_error_naming_the_criteria_file` (the message starts with the criteria file's full path). In `RealPlansTest`, `test_every_real_plan_folder_s_ac_quotes_parse`: for each `~/dev/*/docs/plans/*/spec.md`, `plan_ac_quotes(path)` inside `subTest(path=path)`, a `PlanFormatError` failing that subtest; print `parsed {ok} of {total} real plan folders, {span_count} quoted spans` to stderr.

**File**: `tests/scripts/test_review_loop_criteria_quotes.py` (new)
**Changes**: two classes.

`CriteriaQuoteUnitTest`, on a fake host shaped like `FakeCommentRun`: `test_a_rewritten_line_that_dropped_an_ac_quote_is_put_back_and_files_one_ask_naming_the_ac` (the incident shape above; the file ends `a = 10\n# set the Bash timeout up to 600000 ms\nb = 2\n`), `test_other_edits_in_the_same_file_stay`, `test_an_uneven_rewrite_keeps_the_pass_s_new_lines_and_puts_the_quoted_line_back`, `test_a_moved_span_is_no_removal`, `test_a_span_the_pass_did_not_touch_files_nothing`, `test_an_accepted_ask_lets_the_removal_stand`, `test_a_rejected_ask_keeps_the_put_back_and_files_no_ask`, `test_the_same_ask_is_filed_once_across_rounds`, `test_a_deleted_or_held_file_is_left_alone`, `test_a_finding_that_asks_for_the_change_still_files_an_ask`, `test_the_empty_snapshot_puts_nothing_back`.

`CriteriaQuoteLoopTest(loop_tests.ReviewLoopHarness, unittest.TestCase)`, with no mocks, through the plan header and commit pattern of test_review_loop_script.py:7107. The repo holds `plan.md` and `acceptance-criteria.md`, whose one criterion quotes "limit = 3"; the coder rewrites `app.py` to `limit = 1\nlimit = 20\nlimit = three\nlimit = 4\nlimit = 6\n`.
- `test_loop_puts_back_the_ac_quoted_line_and_keeps_the_fix`: app.py ends `limit = 1\nlimit = 20\nlimit = 3\nlimit = 4\nlimit = 6\n`, and the packet's one ask names that criterion's id, `app.py` and `limit = 3`.
- `test_an_accepted_ask_lets_the_loop_keep_the_removal_and_files_no_new_ask`: header `self.findings_header(accepted)` plus `USER_RULED_HEADER`, where `accepted` is `app.py:3 [plan-drift] Proposed change: <the ask's change text>`; app.py keeps `limit = three` and the packet's `ask == []`.
- `test_a_rejected_ask_keeps_the_put_back_and_files_no_new_ask`, on the two-run pattern of test_review_loop_script.py:5330-5348: run 1 files the ask, then `review_asks.record_rejected_asks([SESSION], realpath(repo), first_packet["ask"], [REJECTED])` and `reset_fake_run()`; run 2 makes the same rewrite; app.py is put back as in the first test, `ask == []`, and one `dropped_asks` entry starts with `REJECTED_ASK_REASON`.
- `test_loop_with_no_plan_on_disk_leaves_ac_text_alone`.
- `test_a_malformed_criteria_file_turns_the_guard_off_with_a_tool_fault_note_naming_the_file`: the AC-quoted edit stands, the run converges, and `tool_fault` names the criteria file's path.

### Success Criteria

A fix pass that rewrites a line holding text an AC quotes ends with that line restored, the pass's other edits kept, and one ask naming the AC, the file and the text. An accepted ask lets the removal stand with no new ask; a rejected one keeps the put-back and files no ask. With no plan on disk the pass's edit stands; a malformed criteria file leaves the edit standing and a `tool_fault` note naming the file.

#### Automated Verification:

- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_protected_lines.py test_plan_format.py test_review_loop_criteria_quotes.py test_review_loop_coder.py test_review_loop_script.py test_review_loop_ruled.py test_phase_asks.py`
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/lib/plan_format.py claude/.claude/scripts/lib/protected_lines.py claude/.claude/scripts/review/review_loop_put_back.py claude/.claude/scripts/review/review_loop_criteria_quotes.py claude/.claude/scripts/review/review_loop_comment_removal.py claude/.claude/scripts/review/review_loop_ruled.py claude/.claude/scripts/review/review_loop_coder.py claude/.claude/scripts/review/review_loop_script.py`

#### Manual Verification:

N/A (the loop-level tests drive the whole script).

---

## Phase 2: The outside-write guard

### Overview

A coder call that writes a file outside the reviewed repo's work tree ends the run in `critical-blocker` naming each path, and the file stays as written.

### Changes Required:

#### 1. The guard

**File**: `claude/.claude/scripts/review/review_loop_outside_writes.py` (new)
**Changes**:
- `OUTSIDE_WRITE_FAULTS: list[str]`, `PASS_OUTSIDE_WRITES: dict[str, list[str]]`, `OutsideWriteError`.
- `scratch_roots(repo, out) -> list[Path]`: resolved `tempfile.gettempdir()`, resolved `/tmp`, resolved `out`; drop a temp root that holds the resolved repo (G1); keep `out`.
- `outside_writes(repo, written, roots) -> list[str]`: a path counts when `script_utils.repo_relative(resolved_repo, name)` is None and its resolved path is under no root; sorted resolved strings.
- `record_pass_writes(role, repo, out, session)`: `session_registry.session_transcript(session)`; None or an `OSError` from `loop_transcript.written_paths` appends the unreadable note to `OUTSIDE_WRITE_FAULTS` and returns (fail-open, stated in a comment); else sets `PASS_OUTSIDE_WRITES[role]` and, when non-empty, appends the writes-found note.
- Mixin `OutsideWrites.stop_on_outside_writes(call_name, findings, result)`: pops `PASS_OUTSIDE_WRITES[call_name]`; empty → return; else `files_touched.update(result.changed)`, `keep_unreverted_open(findings, result.reverted)`, raise `OutsideWriteError` with the blocker text in Approach.

**File**: `claude/.claude/scripts/review/review_loop_coder.py`
**Changes**:
- Inside the `try`, `reply = claude_call_reply(...)` is followed at once by `review_loop_outside_writes.record_pass_writes(role, repo, out, reply.session)`, before the empty-report check, so the success path, the undo-failed path (:142-147, `died=False`) and `NoFinalReportError` all record the pass.
- In `except ModelCallError as error`, call `record_pass_writes(role, repo, out, error.session)` only when `not isinstance(error, NoFinalReportError)` (D10).
- Add `OUTSIDE_WRITE_FAULTS` to `coder_fault_notes`.

**File**: `claude/.claude/scripts/review/review_loop_calls.py`
**Changes**: `ModelCallError` gains a `session` attribute (default `""`); `claude_call_reply` sets it from the reply when one was parsed.

**File**: `claude/.claude/scripts/review/review_loop_partial_fix.py`
**Changes**: `failed_pass_blocker` pops `PASS_OUTSIDE_WRITES[call_name]` and, when non-empty, appends the outside-write blocker text to the died-pass blocker.

**File**: `claude/.claude/scripts/review/review_loop_script.py`
**Changes**: add `OutsideWrites` to the `LoopRun` bases; call `self.stop_on_outside_writes(call_name, findings, result)` right after `self.stop_on_stray_files(...)`.

**File**: `claude/.claude/scripts/review/review_loop_main.py`
**Changes**: add `OutsideWriteError` to the except tuple.

#### 2. Tests

**File**: `tests/scripts/test_review_loop_script.py`
**Changes**: FAKE_CLAUDE prints a unique `session_id` per call (`fake-{key}-{position}`) and always writes `<CLAUDE_CONFIG_DIR or $HOME/.claude>/projects/fake-project/<session>.jsonl` (empty unless `transcript_writes`); new reply keys `transcript_writes: {path: text}` (writes each file and one assistant `Write` tool_use record per path) and `no_transcript: true`; `ReviewLoopHarness.setUp` pops `CLAUDE_CONFIG_DIR` from the child env.

**File**: `tests/scripts/test_review_loop_outside_writes.py` (new)
**Changes**: `test_a_path_in_another_folder_is_outside`, `test_a_repo_path_and_a_relative_path_are_inside`, `test_a_temp_path_is_scratch_when_the_repo_is_not_under_temp`, `test_temp_is_not_scratch_when_the_repo_lives_under_it`, `test_the_out_dir_is_scratch`, `test_a_symlink_into_another_checkout_resolves_outside`, `test_no_transcript_notes_a_fault_and_records_nothing`, `test_an_empty_session_id_notes_a_fault`. Clean `OUTSIDE_WRITE_FAULTS` and `PASS_OUTSIDE_WRITES` with `addCleanup`.

**Files**: `tests/scripts/test_review_loop_scope_guard.py`, `tests/scripts/test_review_loop_coder.py`, `tests/scripts/test_review_loop_script.py`
**Changes**: `ScopeGuardTest.setUp` and `UntrackedDeletionTest.setUp` patch `review_loop_outside_writes.record_pass_writes` (kept as `self.record_writes`, stopped with `addCleanup`); the mocks at test_review_loop_script.py:3532 and :3571 add the same patch to their `with`. Add `ScopeGuardTest.test_an_undo_failure_after_a_finished_pass_still_records_its_outside_writes`: the reply is `CallReply("Fixed.", "s-1")` and the scope guard's `undo` raises; `CoderCallError` is raised and `self.record_writes` was called once with `("coder1", self.repo, self.out, "s-1")`.

**File**: `tests/scripts/test_review_loop_scope_guard.py`
**Changes**: in `ScopeGuardLoopTest`, `test_a_fix_pass_write_outside_the_reviewed_repo_stops_with_a_blocker_and_is_left_in_place` (coder reply `edits: {"app.py": APP_FIXED}` plus `transcript_writes` of a sibling folder's `bin/tool.py`; assert status `critical-blocker`, `blockers[0]` names the resolved path and "did not put them back", the sibling file still holds its text, `app.py` in `files_touched`, `tool_fault` names the path) , `test_a_missing_coder_transcript_notes_a_tool_fault_and_the_run_still_converges` (`no_transcript`; the packet's `tool_fault` holds the note), `test_a_died_fix_pass_that_wrote_outside_the_repo_names_the_path_in_its_blocker` (coder reply `exit: 1` plus `transcript_writes`; the blocker names the resolved path and "did not put them back"), and `test_a_write_through_a_symlink_into_another_checkout_stops_with_a_blocker_naming_the_resolved_path` (the scratch folder holds `sibling/bin/tool.py` and a symlink `link -> sibling`; coder reply `edits: {"app.py": APP_FIXED}` plus `transcript_writes: {"<scratch>/link/bin/tool.py": "x\n"}`; status `critical-blocker`, `blockers[0]` names `<resolved scratch>/sibling/bin/tool.py` and "did not put them back", the file holds `x\n`).

### Success Criteria

A fix pass that writes a file outside the reviewed repo ends the run in `critical-blocker` naming the path, never `converged`, and the file is left as written; a died pass's outside write is named in its blocker; a missing transcript leaves a `tool_fault` note in the packet and the run goes on; no existing harness test gains a note.

#### Automated Verification:

- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_review_loop_outside_writes.py test_review_loop_scope_guard.py test_review_loop_coder.py test_review_loop_script.py test_review_loop_ruled.py test_review_loop_round_two_fixes.py test_review_loop_round_audit.py test_review_loop_repeats.py test_review_loop_named_tests.py test_phase_asks.py`
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/review/review_loop_outside_writes.py claude/.claude/scripts/review/review_loop_coder.py claude/.claude/scripts/review/review_loop_calls.py claude/.claude/scripts/review/review_loop_partial_fix.py claude/.claude/scripts/review/review_loop_script.py claude/.claude/scripts/review/review_loop_main.py`

#### Manual Verification:

N/A (the loop-level test drives the whole script).

---

## Phase 3: Owner lines and the full suite

### Overview

Name the new owners, confirm ticket 1's first half with its existing tests, and run the whole suite.

### Changes Required:

#### 1. Owner lines

**File**: `claude/.claude/scripts/CLAUDE.md`
**Changes**: in the "Review loop parts" line add "text an AC quotes that a fix pass removed, put back with an ask, `review/review_loop_criteria_quotes.py`; files a coder call wrote outside the reviewed repo, `review/review_loop_outside_writes.py`"; in the "Plan text" line add "the spans an AC quotes: `ac_quotes`, `plan_ac_quotes`".

### Success Criteria

The whole suite passes, `plan_ac_quotes` parses every real plan folder, and `review_loop_script.py` stays under 1000 lines. Ticket 1's first half is shown by existing tests (D0.2).

#### Automated Verification:

- [ ] **Evidence** (D0.2; green before this branch): `test_a_stray_file_the_gate_does_not_need_stops_the_loop_and_the_packet_names_file_and_folder` and `test_a_fix_pass_edit_outside_the_review_diff_is_put_back_and_the_packet_names_it` pass unchanged — `python3 tests/parallel_tests.py test_review_loop_scope_guard.py`
- [ ] **Regression gate** (green on today's tree): full suite — `bash tests/run.sh`
- [ ] **Agent-run**: real-plan sweep; report "parsed N of M real plan folders" from `RealPlansTest.test_every_real_plan_folder_s_ac_quotes_parse` — `REAL_PLANS=1 bash tests/run.sh`
- [ ] **Test-verified**: `test "$(wc -l < claude/.claude/scripts/review/review_loop_script.py)" -lt 1000`

#### Manual Verification:

N/A (scripts only).

---

## Phase 4: Close pass

### Overview

`/close-branch`: scripts first, four report-only reviewers in parallel on the whole branch diff, one coder that fixes every finding, a gate on the fix diff, the recap.

### Success Criteria

Quality checks green; every reviewer finding fixed, shown wrong, or (an ask that changes a ticket AC) put to the orchestrating session; the fix-diff gate passed; every acceptance criterion mapped to a test or retired; recap delivered.

#### Automated Verification:

- [ ] **Test-verified**: `bash tests/run.sh`

#### Manual Verification:

N/A (scripts only).

## Testing Strategy

- The AC-quote case table lives in `CriteriaQuoteUnitTest`; the put-back placement cases in `test_protected_lines.py`; the outside-path case table in `test_review_loop_outside_writes.py`.
- Each criterion a user reaches through the loop has a loop-level test with no mocks: the quoted-text put-back, the kept other edits, the accepted and rejected asks, the no-plan run and the malformed criteria file in `CriteriaQuoteLoopTest`; the outside write, the symlinked path, the died pass and the unreadable transcript in `ScopeGuardLoopTest`.
- In-process unit tests patch `record_pass_writes`, so no note leaks between tests.

## References

- ./00-ticket.md, ./02-research.md, ./03-decisions.md
- tests/scripts/test_review_loop_scope_guard.py:1173, :1209 (D0.2 evidence)
