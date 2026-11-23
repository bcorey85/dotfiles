# A review fix pass keeps a ruled owner-line edit; item 2 closes on evidence

> Ticket: ./00-ticket.md
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-22

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

The /code review loop reverts every fix-pass edit to a CLAUDE.md. After this change it keeps an edit to `claude/.claude/scripts/CLAUDE.md` whose only changed lines are added or updated owner bullets under `## Owners`, when the run's decision log held a standing ruling covering owner lines before the pass started, and it reports the kept edit in the packet's dropped asks. Every other CLAUDE.md edit is still reverted. Item 2 (a pasted-brief lane reading owner `user`) does not reproduce; it closes with a replay test that pins the working shape, and no prose rule. Three glossary entries and one change file land with it.

## Phase Status

<!-- Hoisted from below so the first screen answers "where are the agents?". The one section that changes after writing (/code ticks it) — source of truth for "which phase is next". Do not move it back down. -->

- [x] Phase 1: Owner-line grammar and the two-sided diff helper (risk: low)
- [x] Phase 2: Standing rulings learn `covers: owner-lines` (risk: low)
- [x] Phase 3: The review loop keeps a ruled owner-line edit (risk: high)
- [x] Phase 4: Item 2 replay pin, glossary, change file (risk: low)
- [ ] Phase 5: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

Single-slice plan: the contracts (the owner-line grammar, the ruling form, the host fields) are folded into Phases 1 and 2, which are also the walking skeleton. Phase 0 is omitted on purpose.

## Decisions

<!-- One line per block in 03-decisions.md's ## Resolved: `N. [Topic] — [Choice]`, plus `Trade-off: …` only where it changes code. -->

- D1. Grammar location — new `lib/owner_lines.py` owns the path, heading and bullet form; a two-sided changed-line helper goes in `lib/protected_lines.py`. No owner line is added to `scripts/CLAUDE.md`.
- D2. Ruling form — `standing_rulings` `covers:` takes `rewords` or `owner-lines`; `owner_line_ruling(plan_path)` beside `reword_ruling`. Trade-off: the docstring and glossary say "a user's ruling" and now cover a session's.
- D3. Ruling read — pre-pass in `snapshot_approval_blobs`, stored on the host. Trade-off: a ruling written between snapshot and pass is missed and the edit reverted, with the usual reverted-approval-edit row in the packet (Q9).
- D4. Path — exact repo-relative `claude/.claude/scripts/CLAUDE.md`.
- D5. Owner-lines-only — every removed and added line is an owner bullet inside `## Owners`, heading unchanged; a delete, a shrinking replace and a reorder are reverted. Trade-off: a merge of two bullets goes back through the ask.
- D6. Partial edits — any non-owner changed line reverts the whole file.
- D7. Report — a `drop_asks` row with a new reason constant naming the ruling.
- D8. Pre-pass text — read from the work tree in the snapshot.
- D9. Item 2 — no prose rule; a deterministic replay test in `test_plan_format.py`; the phase-1 prose bullet is cut (agent-evals-c3, 2026-11-22).
- D10. First-Source-line fail-open — not fixed here; queued as `criteria-owner-reads-only-the-first-queue-source`.
- Q1. The `## Owners` section stays; this lane adds no line to it.
- Q2. Three glossary edits land in this lane (agent-evals-c3, 2026-11-22).
- Q3. agent-evals-c3's lane briefs write the `covers: owner-lines` line; the change file states its exact form.
- Q4. No failing replay for item 2 exists.
- Q5. D10 is queued, not fixed here.
- Q6. `fix/toolkit-rules-nov22` merges first; the final report names the dependency.
- Q7. A malformed `Standing ruling` line stops the run with a critical blocker naming file and line (agent-evals-c3, 2026-11-22).
- Q8. A merge or reorder of owner bullets reverts and goes through the ask (agent-evals-c3, 2026-11-22).
- Q9. A ruling written mid-pass reverts the edit, listed in the packet as every reverted CLAUDE.md edit is today; no second report path (agent-evals-c3, 2026-11-22).
- Q10. The resume path with a saved approval ask for the file is out of scope (agent-evals-c3, 2026-11-22).
- Q11. The change file is created with the worktree root (plan review, 2026-11-22).
- Q12. The kept row uses `kept_owner_line_text` and a reason that names the ask as dropped, not the edit (plan review, 2026-11-22).
- Q13. AC4's evidence is the real replay on this lane's ticket; the test is regression cover (plan review, 2026-11-22).

## Approaches Considered and Not Taken

The architect named three.

- Read the ruling from the post-pass decision log, as `standing_reword_ruling` does at decision time: a coder pass can add the ruling line and sign-off protection keeps added lines, so the coder would authorize its own edit.
- Make owner-line asks rulable by the session through `phase_asks`: the edit is still reverted and asked about on every pass, which is the asking the ticket wants stopped.
- Loosen `criteria_owner` to any queue path in the ticket text: real briefs name slugs, not paths, so no surveyed shape is fixed, and a user's ticket that mentions a session item would flip to `session`.

## Constraints

<!-- Fixed-before-design non-negotiables. Probe-verified facts an implementation step needs go here with evidence, each tagged `exercised` or `declared-only`. -->

- Script rules (`docs/toolkit-script-rules.md`): snake_case; `bash tests/lint.sh <files>` passes; tests under `tests/scripts/` with paths from `toolkit_paths.py`; run through `python3 tests/parallel_tests.py <file>`; one grammar per format with loud failures; search `lib/` before adding a helper. `exercised`: the rules file is in the tree.
- Off-limits in this lane: `claude/.claude/skills/code/**`, `claude/.claude/scripts/code/**` (so `plan_check.py:48` stays as it is and `reword_ruling` keeps its signature), `claude/.claude/CLAUDE.md`, `orchestration.md`, every CLAUDE.md, `settings.json`. Ruling by agent-evals-c3, 2026-11-22.
- No owner line is added to `claude/.claude/scripts/CLAUDE.md` for the new module; the owner is stated in the module docstring. Ruling by agent-evals-c3, 2026-11-22.
- `review_loop_ruled.py` is 665 lines (`exercised`, `wc -l`), under the 1000-line split rule; the three new methods keep it under.
- Every owner bullet in the in-tree history of the scripts CLAUDE.md (53 added bullets, 45 of them under `## Owners`) and all 26 current ones match `^- <fact>: … \`<dir>/<name>.py\``; the 8 history bullets that do not match are prose bullets outside Owners (`exercised`, the plan reviewer's `git log -p` sweep and the architect's). The grammar is written from that list.
- The run's decision log is `03-decisions.md` beside the plan, or the plan's `## Plan Deviations` section; `standing_rulings(plan_path)` reads both and raises `PlanFormatError name:line:` on a malformed `Standing ruling` line (`exercised`, `lib/standing_rulings.py:27-57`).
- Sign-off protection (`review_loop_signoffs.py`, `protected_lines.entries_missing`) puts back only lost lines; an added line survives a pass. This is why the ruling is read before the pass. `exercised`.
- The loop holds `self.plan` (repo-relative plan path, possibly empty) and `self.repo` (`review_loop_script.py:319`). Both callers of `ask_for_approval_only_edits` (`review_loop_script.py:573-592`, `review_loop_partial_fix.py:205-213`) go through the one method. `exercised`.
- `drop_asks` dedupes by ask (`review_loop_ruled.py:232-235`), so one kept row per file per run. `exercised`.
- Item 2 premise: 7 of 7 lane plans from 2026-11-22 print owner `session`; a survey of 87 local plan tickets finds no pasted-brief ticket reading `user`. `exercised` (`plan_check.py owner` over every `docs/plans/*/00-ticket.md` under `~/dotfiles*`, `~/dev/*`, `~/agent-evals*`).
- The glossary (`docs/glossary.md`) is edited only under agent-evals-c3's ruling of 2026-11-22; no other domain term is coined.
- Change file: `python3 ~/agent-evals/bin/build_changes.py new "<title>" --by claude-code/claude-fable-5-1 --root /home/brandon/dotfiles/docs/changes`, kind `fix` with `test: path::name`, then `build_changes.py`. Sign-offs stay in `03-decisions.md`, never in the change file.
- The ledger's `## Direction & Constraints` holds no line that starts `Standing ruling`, so this plan's own /code review adopts no reword impact by accident (`exercised`, grep after the reword of 2026-11-22).

## External Contracts

<!-- Mandatory: every touched provider/API/platform contract + its invariant + what breaks if violated. "None" stated explicitly. -->

- No provider, API or platform contract is touched. None.
- Internal invariants with a wide blast radius:
  - `standing_rulings.STANDING_RULING_LINE` is the one reader of a ruling line. Widening `covers` to `rewords|owner-lines` keeps every existing `covers: rewords` line parsing; `reword_ruling` still returns only `rewords` rulings, so `code/plan_check.py:48`, `review_fix_plan_impacts.py:205,256` and `review_loop_ruled.py:349` see no change. `declared-only` until Phase 2's consumer tests run (`test_plan_check.py`, `test_review_fix_plan_impacts.py`, `test_handback.py`).
  - `ask_for_approval_only_edits` keeps its signature and return value (the reverted paths). A kept path is in `result.changed` and not in `reverted`, so `files_touched` and `record_skips` behave as for any fixed file. `declared-only` until Phase 3's `test_review_loop_script.py` and `test_review_loop_coder.py` (which covers `review_loop_partial_fix.py`) runs.
  - The packet's dropped-asks row shape `{text, file_line, drop_reason}` (`review_loop_packet.py:59`) is unchanged; only a new reason string appears. `exercised`.
  - A malformed `Standing ruling` line now raises at the first snapshot of any run in a repo that holds `claude/.claude/scripts/CLAUDE.md` (today only when a reword impact appears). The run stops with `critical-blocker` naming file, line and form (`review_loop_main.py:213-215`). Repos without that file never read the decision log in the snapshot.
  - The approval-asks save file, `handback_store` rows and the review-fix state are unchanged.

## Approach

Item 1 is three vertical steps on one path: the grammar (what an owner-lines-only edit is), the ruling (how the decision log grants it), and the loop (where the keep happens). Each step is testable alone and the third wires them end to end through the real `coder_pass` pattern on a temp git repo. Item 2 adds a pin test only. Patterns: a mixin method reads host attributes named in the module docstring; snapshot before the pass, compare after; fail closed on anything unknown (missing text, unreadable file, no ruling, no plan); one form, one reader, `PlanFormatError name:line:`; generic diff helpers in `protected_lines.py` know nothing of meaning.

## Dependencies

- External packages: none.
- Internal: `lib/script_utils.py` `heading_section_indexes`, `work_tree_blob`, `repo_file_paths`; `lib/protected_lines.py`; `lib/standing_rulings.py` (`standing_rulings`, `ruling_label`); `lib/plan_format.py` `PlanFormatError`, `criteria_owner`; `review/review_loop_ruled.py` (`drop_asks`, `approval_ask_text`, `parse_finding`, `snapshot_approval_blobs`, `revert_approval_edit`); `review/review_loop_findings.py` reason constants; tests `approval_host`, `ApprovalEditRevertTest`, `GIT_ENV`, `CriteriaOwnerTest.queue_item`, `StandingRulingTest`, `toolkit_paths`.

## Implementation Plan

Paths are relative to the worktree root. `S` = `claude/.claude/scripts`. Line anchors are from the tree at planning time; re-check them in order as earlier phases land.

### Phase 1: Owner-line grammar and the two-sided diff helper

#### Overview

The format fact gets its owner: a module that knows the scripts CLAUDE.md path, the `## Owners` heading, the bullet form, and decides whether a before/after pair differs only by added or updated owner bullets. The generic diff helper it needs lives beside `changed_stretches`.

#### Changes Required:

##### 1. Two-sided changed-line helper

**File**: `S/lib/protected_lines.py`
**Changes**: Add `changed_line_ranges(before_text, after_text)` above `changed_stretches` (line 24). It returns `(tag, before_start, before_end, after_start, after_end)` for each non-`equal` opcode of `difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)` over `splitlines(keepends=True)`; 0-based, exclusive end; `[]` for equal texts. Rewrite `changed_stretches` as a filter over it: `[(start + 1, end) for tag, start, end, _after_start, _after_end in ranges if tag in ("delete", "replace")]`, behavior unchanged. Name both helpers in the module docstring (lines 1-3); the module still knows nothing of meaning.

##### 2. The owner-line module

**File**: `S/lib/owner_lines.py` (new)
**Changes**:

```python
"""owner_lines.py: the one reader of the owner-line format of the scripts CLAUDE.md (`SCRIPTS_CLAUDE_MD`), and the
test for an edit that only adds or updates owner lines. review_loop_ruled imports it; this module owns the fact."""
import re

import protected_lines
import script_utils

SCRIPTS_CLAUDE_MD = "claude/.claude/scripts/CLAUDE.md"
OWNERS_HEADING = "Owners"
# A bullet that names a fact, a colon, and a backticked module path. Written from every owner bullet ever added.
OWNER_LINE = re.compile(r"^- [^:]+?.*?: .*`[\w./-]+\.(?:py|ts|sh)`")
```

- `owner_line_indexes(lines) -> set[int]`: the 0-based indexes inside `script_utils.heading_section_indexes(lines, OWNERS_HEADING)` whose line matches `OWNER_LINE`.
- `owner_lines_only(before_text, after_text) -> bool`: False when `changed_line_ranges` is empty. For each range, False when `before_end - before_start > after_end - after_start` (a delete, a merge, a drop; a reorder shows as a delete), when any before-index is not in `owner_line_indexes(before_lines)`, or when any after-index is not in `owner_line_indexes(after_lines)`. Else True. Section reads use `splitlines()` without keepends; the counts match. The heading line is never inside its own section, so a changed heading fails.

##### 3. Tests

**Files**: `tests/scripts/test_owner_lines.py` (new), `tests/scripts/test_protected_lines.py`
**Changes**: `test_owner_lines.py` header: `sys.path.insert(0, str(toolkit_paths.LIB_DIR))`, `import owner_lines`. Fixture `SCRIPTS_MD = "# Toolkit scripts\n\n## Owners\n\n- Plan text: \`lib/plan_format.py\`.\n- TOML files: \`lib/toml_file.py\` \`read_toml\`.\n\n## Data between steps\n\n- Steps pass JSON to each other.\n"`. True cases: a bullet added; a bullet's text updated; two bullets each updated. False cases: a prose line added in Owners; a nested `  - x: \`lib/a.py\`` line; a bullet with no backticked module path; an owner-shaped bullet added under Data; a bullet removed; two bullets merged into one; two bullets swapped; the heading renamed; identical texts; a blank line added with the bullet. Real-file test: `(toolkit_paths.REPO_ROOT / owner_lines.SCRIPTS_CLAUDE_MD).is_file()`, every bullet in the real file's Owners section is in `owner_line_indexes`, and the real text plus one inserted bullet is True. In `test_protected_lines.py` `StretchHelpersTest` (line 17): `changed_line_ranges("a\nb\n", "a\nx\ny\n") == [("replace", 1, 2, 1, 3)]`, and equal texts give `[]`.

#### Success Criteria

`owner_lines_only` says True only for an edit that adds or updates owner bullets under `## Owners`, and False for every other shape listed above, on the fixture and on the real file.

#### Automated Verification:

- [ ] **Test-verified**: the owner-line grammar tests pass — `python3 tests/parallel_tests.py test_owner_lines.py`
- [ ] **Test-verified**: the protected-lines tests pass with the new helper — `python3 tests/parallel_tests.py test_protected_lines.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/lib/owner_lines.py claude/.claude/scripts/lib/protected_lines.py tests/scripts/test_owner_lines.py tests/scripts/test_protected_lines.py`

#### Manual Verification:

- [ ] N/A (library code with full test coverage; the end-to-end scenario is Phase 3's)

---

### Phase 2: Standing rulings learn `covers: owner-lines`

#### Overview

The one ruling form gains a second `covers` value and a second reader, so a lane's decision log can grant owner-line edits with a line that fails loudly when malformed.

#### Changes Required:

##### 1. The form and the readers

**File**: `S/lib/standing_rulings.py`
**Changes**: Docstring (lines 1-9): the line form, `covers` is `rewords` or `owner-lines`, a standing ruling is given by the user or the orchestrating session; keep "a cut or a narrowing is never covered" and the no-quote-marks sentence. After line 15 add `COVERS_OWNER_LINES = "owner-lines"`. Line 16: `STANDING_RULING_FORM = "Standing ruling by <who> at <YYYY-MM-DD>: <a short paraphrase, no quote marks> covers: rewords|owner-lines"`. Lines 18-20: the covers group becomes `(?P<covers>{COVERS_REWORDS}|{COVERS_OWNER_LINES})`. Lines 60-65: add `first_ruling_covering(plan_path, covers)` returning the first ruling whose `covers` equals the argument, or None; `reword_ruling(plan_path)` returns `first_ruling_covering(plan_path, COVERS_REWORDS)`; new `owner_line_ruling(plan_path)` returns `first_ruling_covering(plan_path, COVERS_OWNER_LINES)`. `S/code/plan_check.py:48` calls only `reword_ruling` and is not edited.

##### 2. Tests

**File**: `tests/scripts/test_plan_format.py`
**Changes**: Beside `STANDING_LINE` (line 782) add `OWNER_LINES_LINE = "Standing ruling by the orchestrating session at 2026-11-22: owner lines in the scripts CLAUDE.md need no ask covers: owner-lines"`. In `StandingRulingTest`, after the test at 858-865: an owner-lines line in the decision log parses with `covers == "owner-lines"`; `owner_line_ruling` returns it and `reword_ruling` returns None for that plan; with only `STANDING_LINE`, `owner_line_ruling` returns None; with both lines, each reader returns its own. The malformed table (815-831) still raises for `covers: cuts`.

#### Success Criteria

A `covers: owner-lines` line is read by `owner_line_ruling` and ignored by `reword_ruling`; a `covers: rewords` line the reverse; any other `covers` value raises `PlanFormatError` naming file and line.

#### Automated Verification:

- [ ] **Test-verified**: the standing-ruling tests pass — `python3 tests/parallel_tests.py test_plan_format.py`
- [ ] **Test-verified**: every `reword_ruling` consumer still passes — `python3 tests/parallel_tests.py test_plan_check.py test_review_fix_plan_impacts.py test_handback.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/lib/standing_rulings.py tests/scripts/test_plan_format.py`

#### Manual Verification:

- [ ] N/A (library code with full test coverage)

---

### Phase 3: The review loop keeps a ruled owner-line edit

#### Overview

The approval path reads the ruling and the file text before the pass, and after the pass keeps the one edit the ruling covers, reporting it in the packet. Everything else reverts as today. Both callers (live pass and dead pass) go through the one method.

#### Changes Required:

##### 1. The reason constant

**File**: `S/review/review_loop_findings.py`
**Changes**: After line 388 add `KEPT_OWNER_LINE_EDIT_REASON = "no approval ask is needed for an owner-line edit kept under the standing ruling by {ruling}"`, with a comment that it is filled with `standing_rulings.ruling_label(ruling)`. `handback.dropped_ask_warning` (`S/review/handback.py:473-474`) adds `, so it was dropped: <row text>`, so "it" refers to the approval ask, which is dropped, while the edit stands. D7's words "kept under the standing ruling by <who> at <date>" stay inside the reason.

##### 2. The mixin

**File**: `S/review/review_loop_ruled.py`
**Changes**:
- Imports (10-46): `import owner_lines`; add `KEPT_OWNER_LINE_EDIT_REASON` to the `review_loop_findings` import (28-41, alphabetical, before `NOTE_ASK_REASON`).
- Module docstring (1-4): name the exception and the two new host attributes.
- Beside `approval_ask_text` (59-62) add `kept_owner_line_text(path)`, which returns `` f"`{path}:1` [other] owner-line edit kept" ``. It has no `Change:` part and no question, so the packet's `normalize_ask` finds nothing askable, the row prints as a dropped-ask line, and it proposes no revert. For `claude/.claude/scripts/CLAUDE.md` it is 65 characters, under the 80 that `dropped_ask_warning` keeps.
- `init_ruled_state` (197-225): after line 214 add `self.owner_file_before = None` (work-tree text of `owner_lines.SCRIPTS_CLAUDE_MD` before the latest pass; None when absent, unhashed, unreadable or unlisted) and `self.owner_line_ruling = None` (the `{who, at, summary, covers}` ruling read before the latest pass, or None).
- Lines 340-349: extract `plan_path_on_disk()` returning `Path(self.repo) / self.plan` when `self.plan` is set and that file exists, else None; `standing_reword_ruling` uses it. Add `standing_owner_line_ruling()` beside it with the same guard and `standing_rulings.owner_line_ruling`; a malformed line raises `PlanFormatError` as at 342-343.
- `snapshot_approval_blobs` (502-522): at the top reset both new fields to None. After the loop, when `self.approval_blobs.get(owner_lines.SCRIPTS_CLAUDE_MD)` is not None, read the file text into `owner_file_before` (on `OSError` or `UnicodeDecodeError` leave None; comment: fail closed, the edit is then reverted as before) and set `self.owner_line_ruling = self.standing_owner_line_ruling()`. A repo without that file never reads the decision log here. Update the docstring (503-506).
- New `keeps_owner_line_edit(path)` before `revert_approval_edit` (insert before 460). Returns False when `path != owner_lines.SCRIPTS_CLAUDE_MD`, when `self.owner_line_ruling is None`, when `self.owner_file_before is None`, when the work-tree file is missing or unreadable (fail closed), or when `owner_lines.owner_lines_only(before, after)` is False. Otherwise: `label = standing_rulings.ruling_label(self.owner_line_ruling)`; `reason = KEPT_OWNER_LINE_EDIT_REASON.format(ruling=label)`; `self.drop_asks([parse_finding(kept_owner_line_text(path))], reason)`; return True. It touches neither the index nor HEAD.
- `ask_for_approval_only_edits` (366-393): after the ruled-path `continue` (383-384) add `if self.keeps_owner_line_edit(path): continue`. One docstring sentence for the exception.
- `review_loop_script.py:643-644` (`record_skips`): no edit. A kept path is not in `reverted`, so findings on it count as fixed through the normal path.

##### 3. Tests

**File**: `tests/scripts/test_review_loop_ruled.py`
**Changes**: Extract the repo init loop (929-931) and `git_run` (943-944) into module-level `init_repo(repo)` and `git_in(repo, *argv)`; `ApprovalEditRevertTest` uses them. Add `class OwnerLineEditTest(unittest.TestCase)` at line 1110, before `ApprovalAskTextTest`. `setUp` writes and commits `claude/.claude/scripts/CLAUDE.md` (`SCRIPTS_MD`, imported with `from test_owner_lines import SCRIPTS_MD`; `tests/scripts` is already on `sys.path` for `toolkit_paths`), `docs/plans/p/plan.md` (`# Plan\n`) and `docs/plans/p/03-decisions.md` holding the owner-lines ruling line by "the orchestrating session". `coder_pass(edit)`: `approval_host(reverts=True)`, `host.repo`, `host.plan = "docs/plans/p/plan.md"`, `files_touched = set()`, `snapshot_approval_blobs()`, `edit()`, `ask_for_approval_only_edits([SCRIPTS_CLAUDE_MD], [])`.

`test_only_an_owner_line_edit_stands_under_the_ruling` (the ticket's test; fails before, passes after), one `subTest` per case, each case first rewriting the original text: (a) owner bullet added: kept; (b) owner bullet updated: kept; (c) prose bullet added under Data: reverted; (d) owner bullet plus prose line: reverted; (e) owner bullet removed: reverted. Each case asserts the file text (edited or original), `host.user_only_asks == []`, and the dropped reasons: `[KEPT_OWNER_LINE_EDIT_REASON.format(ruling="the orchestrating session at 2026-11-22")]` for (a) and (b), `[REVERTED_APPROVAL_EDIT_REASON]` for the rest. Case (f), AC5's live shape: an owner bullet added with one finding located on `claude/.claude/scripts/CLAUDE.md` passed as `findings`; kept, `user_only_asks == []`, and `ask_for_wanted_changes` files no ask for the path (it is not in `reverted`).

`test_the_packet_line_reports_the_kept_edit_and_proposes_no_revert` (fails before, passes after) asserts the exact packet line. It runs case (a)'s owner bullet through `coder_pass`, then `message = review_loop_packet.packet_message({"status": "converged", "dropped_asks": host.dropped_asks})` (the pattern at 916-918), and asserts `handback.load(message)["dropped_asks"] == ["no approval ask is needed for an owner-line edit kept under the standing ruling by the orchestrating session at 2026-11-22, so it was dropped: '`claude/.claude/scripts/CLAUDE.md:1` [other] owner-line edit kept'"]` as a literal string, plus `"revert" not in` that line. Also: `handback.load(message)["ask"] == []`.

Guard tests (pass before and after): a ruling the pass adds keeps nothing (no ruling at snapshot; `edit` appends the ruling line and an owner bullet; the CLAUDE.md edit is reverted); a rewords-only ruling keeps nothing; `host.plan = ""` keeps nothing; an owner-shaped edit to `other/scripts/CLAUDE.md` (committed in setUp with an Owners section) is reverted under the ruling; a committed owner-line edit stays committed (`git commit -am` inside `edit`; file and HEAD keep the edit, `files_touched == set()`, kept reason); a file unreadable at judging time is reverted (`edit` deletes the work-tree file; after the pass the file holds the original text and the dropped reason is `REVERTED_APPROVAL_EDIT_REASON`); a malformed ruling (`Standing ruling by x at 2026-11-22: y covers: everything`) makes `snapshot_approval_blobs()` raise `plan_format.PlanFormatError`.

#### Success Criteria

Under a pre-pass `covers: owner-lines` ruling, a fix-pass edit to `claude/.claude/scripts/CLAUDE.md` that only adds or updates owner bullets stays in the work tree with no user ask and one kept row in the dropped asks; a non-owner edit, a mixed edit, a removed bullet, an edit to another `scripts/CLAUDE.md`, a ruling the pass itself adds, a rewords-only ruling and a run with no plan all revert as today.

#### Automated Verification:

- [ ] **Test-verified**: the ruled-findings tests pass, the owner-line case table included — `python3 tests/parallel_tests.py test_review_loop_ruled.py`
- [ ] **Test-verified**: both callers and the packet still pass — `python3 tests/parallel_tests.py test_review_loop_script.py test_review_loop_coder.py test_protected_lines.py`
- [ ] **Lint-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/review/review_loop_ruled.py claude/.claude/scripts/review/review_loop_findings.py tests/scripts/test_review_loop_ruled.py`

#### Manual Verification:

- [ ] N/A (the temp-repo tests drive the real git path end to end; no live run is needed)

---

### Phase 4: Item 2 replay pin, glossary, change file

#### Overview

Item 2 closes on evidence with a test that pins the shape that works; the glossary gains the three ruled edits; the change file records item 1 and states the exact ruling line for lane briefs.

#### Changes Required:

##### 1. Item 2: real replay plus regression cover

**Real replay (AC4).** This lane's own ticket, `docs/plans/review-owner-1122/00-ticket.md`, is a pasted-brief lane ticket. The lane's phase 1 wrote one `Source:` line per queue item without being told to, as all 7 lane tickets of 2026-11-22 did. `plan_check.py owner` on this plan prints owner `session`. The replay reads each queue file locally (`plan_format.queue_item_author`, which needs `~/agent-evals/queue/<slug>.md` to exist), so it holds only while `~/agent-evals` is on a branch that has both items, as `bench-base` does now.

**Regression cover.**
- **File**: `tests/scripts/test_plan_format.py`
- **Changes**: In `CriteriaOwnerTest`, after the test at 627-632, add `test_a_pasted_brief_lane_ticket_with_one_source_line_per_item_is_session_owned`.
  - Two queue items `a` and `b` via `self.queue_item(..., slug=)`, both generated by `claude-code/x`.
  - Write `00-ticket.md` shaped like this lane's own ticket: a `# Lane brief: x` title; two `Source: ~/agent-evals/queue/<slug>.md` lines; a `## Brief (verbatim)` section that names the slugs and a `git -C ~/agent-evals show origin/bench-base:queue/<slug>.md` line; two `## Queue item N (verbatim)` sections, each with a pasted `---\ntype: "QueueItem"\n…---` block and a `## Done when` list.
  - Copy no words from the real ticket.
  - Assert `owner == CRITERIA_OWNER_SESSION` and `source == "~/agent-evals/queue/a.md"`.
- This is regression cover for the shape lanes write: the pasted frontmatter blocks and the brief's slug lines never change the owner read from the `Source:` lines.

**Limit.** Neither the test nor the replay can fail against item 2's premise. Both hold `Source:` lines that a session wrote, and the premise is that those lines are missing. No failing replay exists (Q4), and the item closes on that evidence (D9).

##### 2. Glossary

**File**: `docs/glossary.md`
**Changes**: Line 147 (approval-only file): "A file a coder edits only after the user's own ruling, such as a CLAUDE.md. An owner-line edit to the scripts CLAUDE.md stands under a standing ruling that covers owner lines." Line 145 code ref: add `claude/.claude/scripts/review/review_loop_ruled.py`. Line 201 (standing ruling): "A ruling, by the user or the orchestrating session, that covers every later reword of an AC or every owner-line edit." New entry under `## Dotfiles` before `### template` (line 313): `### owner line`, `_noun_ · \`OWNER_LINE\` in \`claude/.claude/scripts/lib/owner_lines.py\``, "A bullet under `## Owners` in the scripts CLAUDE.md that names the module owning a fact."

##### 3. Change file

**File**: `docs/changes/notes/2026-11-22-<slug>.md` (created in this worktree by `python3 ~/agent-evals/bin/build_changes.py new "A review fix pass keeps an owner-line edit to the scripts CLAUDE.md under a standing ruling" --by claude-code/claude-fable-5-1 --root /home/brandon/dotfiles-review-owner-nov22/docs/changes`; filled, then the pages rebuilt with `python3 ~/agent-evals/bin/build_changes.py --root /home/brandon/dotfiles-review-owner-nov22/docs/changes`; nothing is written to the main checkout)
**Changes**: `change_type: "fixed"`, `kind: "fix"`, `components: ["script/review-loop-ruled", "script/standing-rulings", "script/owner-lines"]`, `evidence: ["queue item"]`, `test: "tests/scripts/test_review_loop_ruled.py::OwnerLineEditTest.test_only_an_owner_line_edit_stands_under_the_ruling; tests/scripts/test_plan_format.py::CriteriaOwnerTest.test_a_pasted_brief_lane_ticket_with_one_source_line_per_item_is_session_owned"` (the `path::Class.test` form the existing notes use). `## Change` states: the exact line `Standing ruling by <who> at <YYYY-MM-DD>: <paraphrase, no quote marks> covers: owner-lines`; where it goes (the lane's `03-decisions.md` or the plan's `## Plan Deviations`); that it is in place before the pass; that only adds and updates inside `## Owners` stand; item 2's close on evidence with the pin test; the three glossary edits; the merge dependency on `fix/toolkit-rules-nov22`. Back-out: revert the commit and remove any `covers: owner-lines` line from plans, which would then raise `PlanFormatError`. No sign-off text; those live in `03-decisions.md`.

#### Success Criteria

The pin test passes; the glossary holds the three entries; the change file passes the builder's check and names both tests and the exact ruling line.

#### Automated Verification:

- [ ] **Test-verified**: the regression cover passes — `python3 tests/parallel_tests.py test_plan_format.py`
- [ ] **Replay-verified**: this lane's pasted-brief ticket prints owner `session` (needs `~/agent-evals` on `bench-base` or any branch holding both queue items) — `python3 claude/.claude/scripts/code/plan_check.py owner docs/plans/review-owner-1122/spec.md | jq -e '.owner == "session"'`
- [ ] **Presence-verified**: the glossary contains the owner line entry — `rg -q '^### owner line$' docs/glossary.md`
- [ ] **Presence-verified**: the glossary contains the widened standing ruling — `rg -q 'or every owner-line edit' docs/glossary.md`
- [ ] **Presence-verified**: a change note contains the exact ruling line form — `rg -l 'covers: owner-lines' docs/changes/notes`
- [ ] **Build-verified**: the change pages build — `python3 /home/brandon/agent-evals/bin/build_changes.py --root /home/brandon/dotfiles-review-owner-nov22/docs/changes`
- [ ] **Agent-run**: full suite under the memory cap, in the background — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] N/A (text and test changes; `/verify-branch` reads the files)

---

### Phase 5: Close pass

**Close pass** (risk: high) — `/close-branch`: scripts first, then four report-only reviewers in parallel on the whole branch diff (correctness, structure, test intent, plan and acceptance-criteria reconciliation), ONE `coder` that fixes every finding and writes every owed test, then a report-only gate on the fix diff alone, then the recap sheet. Root-cause rule: a cast or default papering a fixable loose structure is a finding; fix the source.

#### Success Criteria

Quality checks green; every reviewer finding fixed, shown wrong, or (an ask that changes a ticket AC) put to agent-evals-c3 as criteria owner; the fix-diff gate passed; every acceptance criterion mapped to a test or explicitly retired; concentration counts stated; recap and smoke-test checklist delivered. The real diff size is reported against the estimate of about 400 changed lines (about 130 code, 230 tests, 40 docs and change file).

#### Automated Verification:

- [ ] **Test-verified**: the suite passes — `bash tests/run.sh`

#### Manual Verification:

- [ ] N/A (review phase)

## Acceptance Criteria

- **Criteria file**: `docs/plans/review-owner-1122/acceptance-criteria.md`

## What We're NOT Doing

- `criteria_owner` reading every Source line (D10): queued as `criteria-owner-reads-only-the-first-queue-source`.
- Any eng-spec phase-1 prose edit or rule-meter arms (D9, ruling by agent-evals-c3 at 2026-11-22; this cuts the item's phase-1 "Done when" bullet).
- Edits to `orchestration.md`, `claude/.claude/CLAUDE.md`, `S/code/**`, `claude/.claude/skills/code/**`.
- Partial keeps of a mixed edit (D6).
- Resume-path handling of a saved approval ask for the scripts CLAUDE.md from an earlier run.
- Index-versus-work-tree divergence (only work-tree text is classified).
- Who writes the ruling line in lanes not started by agent-evals-c3 (Q3).

## Testing Strategy

Real-git temp repos through the existing `coder_pass` pattern for the loop; pure-function case tables for the grammar and the ruling reader; a replay fixture for item 2 shaped like this lane's own ticket. Every Phase 1-3 test that pins new behavior fails on the current tree. Consumer suites of `reword_ruling` and of `ask_for_approval_only_edits` run unchanged as regression gates.

## Refactor Candidates

- `restore_protected_lines` builds its own `SequenceMatcher` and needs the equal opcodes too; leave it.
- `approval_only_paths` and `owner_lines.SCRIPTS_CLAUDE_MD` both describe CLAUDE.md files; if more file-specific exceptions appear, move approval-file facts into one lib owner.

## Plan Deviations

Phase 1 ruling (Ticket #AC7 criterion, owner session): owner_lines_only requires a replaced owner bullet to resemble its old text (similarity >= REWRITE_RATIO); ruled by the orchestrating session, 2026-11-22.

Phase 3 held impact (narrow, no AC change): a fix pass could write the owner-lines ruling that a later round of the same run reads; deferred to phase end by the orchestrating session, 2026-11-22.

## References

- ./00-ticket.md, ./01-questions.md, ./02-research.md, ./03-decisions.md
- `docs/toolkit-script-rules.md`, `claude/.claude/scripts/CLAUDE.md`
