---
date: 2026-11-22
git_commit: 4a1126ae3ffe829e4e385efff133d43ad6b61a47
branch: fix/review-owner-nov22
topic: Review-loop file handling of fix passes, approval-only and sign-off protection, decision-log rulings, criteria owner, ticket snapshot, queue items, rule-meter harness, change files
tags: [review-loop, review_loop_ruled, signoff, protected-lines, standing-rulings, plan_check-owner, queue, rule_meter, docs-changes]
status: complete
---

# Research: Review-loop file handling, ruling records, criteria owner, queue, rule-meter, change files

Paths are relative to `/home/brandon/dotfiles-review-owner-nov22`; `S` = `claude/.claude/scripts`. Agent-evals paths are under `~/agent-evals`.

## Findings

### 1. How `review_loop_ruled.py` handles the files a fix pass changed

The module is a mixin (`class RuledFindings`, `S/review/review_loop_ruled.py:183`) for `LoopRun`. There is no single "keep / revert / ask" function. The flow is spread over several call sites in `review_loop_script.py`.

Pass sequence (`S/review/review_loop_script.py`, the coder-pass method around 565-594):
1. Before the pass: `self.snapshot_approval_blobs()` (line 573), `snapshot_signoffs(...)` (574), `snapshot_comments(...)` (575).
2. `coder_call(...)` (583).
3. `self.undo_protected_edits(signoffs, comments, findings)` (590 area: puts sign-off lines and comment lines back; `S/review/review_loop_comment_removal.py:80-86`), then `without_put_back(...)`.
4. `self.flag_broken_no_code_rulings(findings, result.changed, nits)` (`review_loop_script.py:590`).
5. `reverted = self.ask_for_approval_only_edits(result.changed, findings)` (`review_loop_script.py:591`).
6. `without_reverted(result, reverted, stats_before)` then `check_pass_result`.

The dead-pass path (`S/review/review_loop_partial_fix.py:205-213`, `failed_pass_blocker`) runs the same `undo_protected_edits`, `flag_broken_no_code_rulings` and `ask_for_approval_only_edits` on `error.changed`.

`ask_for_approval_only_edits(changed, findings)` (`review_loop_ruled.py:366-393`):
- `ruled_paths = self.approval_ruled_paths(findings)` (379).
- For each path in `approval_only_paths(changed)` (382):
  - KEEP: `if path in ruled_paths or self.names_ruled_wanted_target(path, findings): continue` (383-384). The edit stays as the coder left it ("the ruling is the approval").
  - REVERT: `if self.revert_approval_edit(path): reverted.append(path); continue` (385-387).
  - ASK (revert failed or base unknown): `self.file_approval_ask(path, self.approval_base(path)); filed = True` (388-389).
- `wanted_filed = self.ask_for_wanted_changes(findings, reverted)` (390): one user-only ask per finding on a reverted path.
- `save_approval_paths()` if anything was filed (391-392). Returns `reverted`.

`revert_approval_edit(path)` (460-485):
- `base = self.approval_base(path)`; `UNKNOWN_BASE` returns False (469-471, fail closed). `approval_base` (453-458) returns `UNKNOWN_BASE` if `not self.approval_snapshot_ok or path in self.approval_unhashed`, else `self.approval_blobs.get(path)` (None = file created by the pass).
- Computes `content_changed` (`script_utils.content_changed_since`), `index_changed` (`script_utils.index_entry` vs saved), `committed` (`committed_during_pass`, 493-500). None of the three: returns True, no revert needed (476-477).
- `script_utils.restore_blob` for content, `script_utils.restore_index_entry` for the index; either failing returns False (478-481).
- If `committed`, `self.files_touched.add(path)` (482-483).
- `drop_asks([parse_finding(approval_ask_text(path))], REVERTED_APPROVAL_EDIT_REASON)` records the revert in the packet's dropped asks (484). Returns True.

`ask_for_wanted_changes` (395-414) builds a `parse_finding(...)` ask per finding on a reverted path (via `findings_on_reverted_paths`, 487-491) with text "A fix coder wants to edit `path` for the finding "<title>", which needs the user's approval. Change: ... `wanted_edit_target(path)`"; `file_wanted_ask` (416-435) dedupes (`repeats_a_wanted_ask` 437, `rejected_a_wanted_ask` 444), calls `self.add_ask(CODER_GATE, ask)`, appends to `self.user_only_asks` and `self.wanted_entries`.

`file_approval_ask` (536-546): `add_ask(CODER_GATE, ask)`, appends to `user_only_asks`, `user_only_paths`, and `user_only_bases.setdefault(path, base)`.

Other per-file handling in the same module:
- `flag_broken_no_code_rulings` (605-628): for code (non-`is_doc_path`) files changed against a no-code ruling, appends `{"ruling", "file"}` to `self.no_code_broken` via `broken_ruling_finding` (90-98).
- `mark_standing_rewords_applied(changed)` (327-338): marks reword impacts applied when `changed` intersects the plan file or `acceptance-criteria.md` beside it.
- `not_applied_why` / `unapplied_adopted` (121-147): adopted findings with no diff in their file are `Unapplied` (`NamedTuple(finding, blocker)`, 109-111); `stop_on_unapplied` (630-637) stops "critical-blocker".
- Resume: `snapshot_approval_blobs` (502-522), `resume_approval_asks` (556-584), `resume_wanted_asks` (586-594); saved through `approval_asks_store.write_saved_asks` / `read_saved_asks` (imported 16-24; saved by `save_approval_paths`, 548-554).

### 2. Approval-only files: definition and consumers

- Definition: `PROMPT_MARKDOWN_NAMES = {"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md"}` at `S/lib/format_files.py:25`.
- Consumer 1: `approval_only_paths(changed)` returns paths whose `PurePosixPath(path).name` is in that set (`S/review/review_loop_ruled.py:52-56`; import at line 26). Used at 382 (`ask_for_approval_only_edits`) and 516 (`snapshot_approval_blobs`, over `script_utils.repo_file_paths`).
- Consumer 2 (same set, different purpose): `format_files.is_prompt_markdown` (`S/lib/format_files.py:392-399`), which also matches `.claude` folder and `.config/opencode/` prefix; not used by the review loop.
- The set matches by basename at any depth; `NOT_CLAUDE.md`, `docs/CLAUDE.md.bak`, `claude.md` do not match (`tests/scripts/test_review_loop_ruled.py:58-64`).
- `ask_outcome_words.py` ties the reason text to it: `APPROVAL_REASON = "a fix coder edited an approval-only file"` (`S/lib/ask_outcome_words.py:166`), `USER_ONLY_KEY = "user_only"` (163), `user_only_reason` (204-209).
- Ask text: `approval_ask_text(path)` (`review_loop_ruled.py:59-62`) = "`{path}:1` [other] A fix coder edited `{path}`, which needs the user's approval. Change: {approval_change(path)}" (`approval_change` from `approval_asks_store`).
- Sign-off protection is a separate path set (decision logs); see Q3.

### 3. Protected and sign-off lines

Modules and flow:
- `S/lib/protected_lines.py` (109 lines, "knows nothing about what the lines mean"): `REWRITE_RATIO = 0.6` (7), `entries_missing(before_entries, after_entries)` (10), `changed_stretches(before_text, after_text)` (24), `consecutive_runs(entries)` (36), `in_span_with(number, spans, named_lines)` (47), `restore_protected_lines(before_text, after_text, protected_numbers, whole_stretch=True, may_replace=None)` (55), `rewritten_stretch` (80), `closest_line` (97). Uses `difflib.SequenceMatcher(autojunk=False)` opcodes: `delete` restores the stretch whole (or only protected lines when `whole_stretch=False`); `replace` puts each protected line over its closest rewrite (ratio >= 0.6, optionally gated by `may_replace`), unmatched ones go in front.
- `S/lib/signoff_lines.py` (80 lines): `signoff_lines(text, name="")` (176) returns `[(1-based line number, line text)]`. Marker test `is_signoff_marker` (127) uses `RULED_BY` (120; `rul(ed|ings?)|adopted|decided|cut|reworded|narrowed` + `by`), `SIGNED_OFF` (121), `plan_format.SESSION_RULING_MARK` (`sign-off`, `ruled`, `ruling`; `S/lib/plan_format.py:1604`), `RULING_TEXT_LINE` (122, `The ruling:`). Entry extent: `entry_start` (134), `continuation_end` (144; stops at blank, unindented line, `The disagreement:` line, or a bullet at the entry's own indent or above). Scope: `signoff_scope_indexes(name, lines)` (161): every line of `03-decisions.md` (`plan_format.DECISION_LOG_NAME`); the `## Plan Deviations` section when the file has one; none for `plan.md`, criteria, spec, questions, research files or `*00-ticket.md` without such a section; every line of any other file.
- `S/review/review_loop_signoffs.py` (177 lines; the 366-line number in my read is the concatenation offset, the file ends at its line 177):
  - `is_decision_log(path)` (210): basename `03-decisions.md` or path containing `docs/plans/`.
  - `recorded_signoff_lines(path, text)` (216), `in_signoff_scope` (221), `signoff_entry_line` (230), `finding_hits_signoff(repo, finding)` (242), `signoff_ask(repo, finding)` (257).
  - `class SignoffSnapshot(typing.NamedTuple)` with `texts: dict`, `lines: dict` (264-268); `snapshot_signoffs(repo, extra_paths)` (271) globs `docs/plans/**/*.md` plus `extra_paths` that are decision logs; stores only files that hold at least one sign-off line.
  - `lost_lines(before_entries, after_text, path="")` (289) uses `protected_lines.entries_missing`.
  - `class SignoffRuns` (301): `split_signoff_items` (304; adopted items skip it, `self.adopted`), `without_put_back` (317), `put_back_undid` (331), `not_put_back` (341), `undo_signoff_pass(snapshot, findings, skip)` (345): for each snapshot file not in `skip`, reads current text, `lost_lines`, then `put_back_lines(repo, path, snapshot.texts[path], current, lost_numbers)` and files one ask per lost line (`PUT_BACK_NOTE`, 207; asks via `add_ask(CODER_GATE, ...)`).
  - Constants: `SIGNOFF_ASK_NOTE` (206), `PUT_BACK_NOTE` (207).
- `S/review/review_loop_put_back.py`: `class ProtectedPutBack(typing.NamedTuple)` fields `path`, `lost_numbers`, `before_text`, `restored_text`, property `unchanged` (10-22); `put_back_lines(repo, path, before_text, current, numbers, whole_stretch=True, may_replace=None)` (25) restores and writes atomically; `fully_put_back_paths(put_back)` (33).
- Data shapes: changed/classified line = `(int number, str text)` tuples in lists (`entries`); "protected" = 1-based numbers of the earlier text; classification output is the list from `signoff_lines` (all sign-off lines) and `entries_missing` (those lost).
- Wiring: `review_loop_comment_removal.py:80-86` `undo_protected_edits` calls `undo_signoff_pass(signoffs, findings, held)` then `undo_comment_pass`; `review_loop_script.py:133` imports `SignoffRuns, snapshot_signoffs`; `review_loop_script.py:496` calls `split_signoff_items` before the coder.
- `review_loop_signoffs.py` imports `CODER_GATE` from `review_loop_ruled` (line 204).

### 4. Decision log recording and readers

On disk (plan-impact rulings). Writer `plan_format.ruling_deviation(phase, decision, owner, ruled_at, ruling_words, disagreement)` (`S/lib/plan_format.py:904-912`) produces:

```
- YYYY-MM-DD: <decision>. Ruled by <owner> at YYYY-MM-DD HH:MM.

  The ruling: <ruling words, one line>

  The disagreement:
  <impact text lines, indented>
```
(`- YYYY-MM-DD (Phase N): ...` when a phase is given.) `DEVIATION_RULING_PREFIX = "  The ruling: "` (`plan_format.py:88`). Entries go to the plan's `## Plan Deviations` section (`DEVIATIONS_HEADING`, line 61) via `plan_format.append_deviation`; callers: `review/review_fix_plan_impacts.py:105-121` (`write_ruling_entry`) and `review/review_fix_asks.py:315-333` (`accepted_ask_deviation_lines`). Decision words: `DECISION_WORDS` (adopt/keep/discuss -> "Adopt plan change" etc.).

Who ruled (`plan_format.ruling_owner(repo_dir, by)`, 864-868): `by != "user"` returns `SESSION_RULING_OWNER = "the session, not the user"` (62); `by == "user"` returns `git config user.name` or `"the user"`. `USER_RULING = "user"`, `SESSION_RULING = "session"` (861-862).
- Session ruling on disk: `Ruled by the session, not the user at 2026-11-22 13:35.`
- User ruling on disk: `Ruled by <git user.name> at <time>.`
- Relayed user ruling: `review_fix_plan_impacts.relayed_owner` (97-102) appends `, relayed by session <name> (user turn at <timestamp>)` to the owner.
- Stored rows: `handback_store.record_ruled_impact(..., owner=, ruled_at=)`, `record_relayed_plan_ruling` (`review_fix_plan_impacts.py:113-119`), `record_relayed_ruling` (`review/ruling_relay.py:102`).

Readers:
- `S/lib/standing_rulings.py` (93 lines): standing ruling line form `Standing ruling by <who> at <YYYY-MM-DD>: <paraphrase, no quote marks> covers: rewords` (constants `STANDING_RULING_FORM` 16, regexes 17-20); `standing_rulings_in(lines, name, indexes=None)` (27; a line starting `Standing ruling` that fails the form raises `plan_format.PlanFormatError` with `name:line:`); `standing_rulings(plan_path)` (46: `## Plan Deviations` section, then `03-decisions.md` beside it); `reword_ruling(plan_path)` (60); `impact_rewords_criterion` (68), `impact_blocks` (74), `block_rewords_criterion` (83), `ruling_label(ruling)` (91). `COVERS_REWORDS = "rewords"`, `REWORD_KIND = "reword"`. Consumer: `review_loop_ruled.py:318,340-349,363`.
- `S/lib/ruled_change_text.py` (62 lines; imports stdlib only): `USER_CLAUSE = "The user changed it"`, `SESSION_CLAUSE = "The session changed it, not the user"`, `UNNAMED_CLAUSE = "It was changed at the ruling"`, `PLACE_MARKER = "; make this change in its place: "` (98-101); `changed_text(base, note, ruler_clause)` (114), `ruled_note(finding_text)` (119, text after the last marker), `is_no_code_ruling(note)` (138), `is_no_code_finding(finding_text)` (150), `asks_for_test_edit` (128). This tells a user ruling from a session ruling in a finding's text by the ruler clause; the note itself is after the marker. Consumer in the loop: `is_approval_ruling` (`review_loop_ruled.py:596-603`): user-ruled texts always count as approval; session-ruled count only if the text holds `approval_change(finding.path)` and `ruled_note(finding.text) is None`.
- `S/lib/ask_outcome_words.py` (65 lines; stdlib only): `ACCEPTED`, `REJECTED`, `APPLIED`, `HELD` (160-175), `USER_ONLY_KEY`, `CRITERIA_KEY`, `USER_ONLY_MARK`, `PHASE_ASKS_PATH`, `LIST_COMMAND`, `OUTCOME_PLACEHOLDER`, `RELAYED_BY_FLAG = "--relayed-by"`, `RETIRED_QUOTE_FLAG = "--quote"`, `RELAY_USAGE`; `rule_command(count, by_user=False)` (191), `user_only_numbers` (199), `user_only_reason` (204), `rule_instruction(asks)` (212). `--by user` records the user's own ruling; a session's call is `--by session` (default).
- `S/lib/signoff_lines.py` reads the log for sign-off lines (Q3). `review/review_loop_signoffs.py` consumes it.
- Relay verification: `S/review/ruling_relay.py` (`REFUSAL_PREFIX` 18, `RelayRequest`, `record_relay` 93, `human_turn_lookup.verified_human_turn` 89).
- The decision log itself is named by `plan_format.DECISION_LOG_NAME = "03-decisions.md"` (`plan_format.py:1555`). Other writers in skills: `eng-spec/phases/2-research.md:39`, `6-finalize.md:18,30`, `6b-review.md:38`.

### 5. `claude/.claude/scripts/CLAUDE.md` today

49 lines. Structure: `# Toolkit scripts` (1); intro line 3 ("Each fact below has one owner. Import it. Never add a second copy..."); `## Search first` (5) with one paragraph (7); `## Owners` (9) with bullets at lines 11-36; `## Data between steps` (38) bullets 40-42; `## Failures and writes` (44) bullets 46-49. Line 37 and 43 are blank; there is no line 2/4/etc. text beyond blanks.

Bullet shapes in Owners (`- <what the fact is>: <owner pointer>` form):
- Fact label, colon, then `` `path/module.py` `` with function/constant names in backticks and parenthesised lists: e.g. line 11 `` `review/handback.py` `CLEAN_STATUSES` and `false_clean_reason` ``; line 21 `` `lib/check_scope.py` (`runs_tests`, `runner_family`, ...) ``.
- Multi-owner sentences separated by `;` or `.` within one bullet: line 13 (tree identity, three owners), line 15 (review loop mixins: "a reviewer's findings taken in, `review/review_loop_intake.py`; ..."), line 22 (shell parsing, many owners), line 23.
- Single-sentence bullet with a prohibition: line 25 "A lock held across processes: `lib/file_lock.py`. Never write a second flock helper."; 26, 32.
- Bullet naming module plus a property: line 24 (`lib/ask_outcome_words.py`, "which imports nothing"), 28, 29, 30 ("standard library only").
- Bare pointer: 14, 31.
- The rulings/sign-off owners are in line 30: "Text for a changed or no-code ask ruling on a finding ...: `lib/ruled_change_text.py` (`changed_text`, `ruled_note`, `is_no_code_ruling`), standard library only. The sign-off lines of a decision log: `lib/signoff_lines.py`; a standing ruling's form and reader: `lib/standing_rulings.py`; a coder pass never edits a sign-off line: `review/review_loop_signoffs.py`, which puts changed lines back through `lib/protected_lines.py`." Line 31: "Plan text: `lib/plan_format.py`." Line 24 is the ask outcome words owner.
- Data/Failures sections use imperative rule sentences ("Never ...", "A gate picks ..."), not owner pointers; line 49 points at `tests/scripts/` and `tests/scripts/toolkit_paths.py`.
- The `docs/toolkit-script-rules.md` file includes this file with `@~/dotfiles/claude/.claude/scripts/CLAUDE.md` (line 3).

### 6. Tests for `review_loop_ruled.py` and mixins

Files under `tests/scripts/`:
- `test_review_loop_ruled.py` (1363 lines): classes `ApprovalOnlyPathsTest` (57), `ApprovalAskFilingTest` (79), `ApprovalRulingTest` (91), `ApprovalAskUserOnlyTest` (137), `ApprovalAskResumeTest` (154), `RewordFlagTest` (823), `ApprovalEditRevertTest` (920), others beyond.
- `test_review_loop_script.py`: `RepeatFilterHost` (290), `ReviewLoopHarness` mixin (617; scratch repo `shop-api`, fake `claude` and `ruff` on PATH, `commit_files` 656), `SignoffLinesLoopTest` (6286, `run_loop` 6294), further harness users (`run_loop` 6463).
- `test_protected_lines.py` (86 lines; also tests `review_loop_signoffs`; `BEFORE` constant line 14).
- `test_ruled_change_text.py` (119), `test_review_user_ruled.py` (426; `DropPacketUserRuledMarksTest` 95, `LeaveOutRuledImpactsTest` 157), `test_review_loop_findings.py` (`RuledImpactTest` 128), `test_review_loop_prompt_file.py` (`UserRuledTimeTest` 16), `test_review_loop_coder.py`, `test_review_loop_round_two_fixes.py`, `test_review_loop_named_tests.py`, `test_review_loop_closure.py`, `test_ruling_relay.py`.
- `test_plan_format.py`: `StandingRulingTest` (789), `SignoffLinesTest` (1396). No `test_standing_rulings.py`, `test_signoff_lines.py` or `test_ask_outcome_words.py` file exists.

Fixtures and helpers in `test_review_loop_ruled.py`: `ruled_finding(note, location="`a/b.py:3`")` (38; builds via `ruled_change_text.changed_text(..., USER_CLAUSE)` + `parse_finding`), `broken_entry(finding, path)` (43), `class Host(review_loop_ruled.RuledFindings)` (47; `repo="/repo"`, `plan=""`, `plan_impacts=[]`, `resolved_texts=[]`, `init_ruled_state()`), `approval_host(user_ruled=(), session_ruled=(), reverts=False)` (67; stubs `revert_approval_edit`, wires `add_ask` to `LoopRun.add_ask`), `ApprovalAskResumeTest.setUp` (git repo in tempdir with `CLAUDE.md`), `.git`, `.host`, `.edit_claude_md`, `.saved_paths` (154-186). Imports `from no_code_notes import NO_CODE_NOTES` and `from test_review_loop_script import APP_FIXED, CLEAN_REVIEW, CLOSED, SESSION, ReviewLoopHarness`; `tests/scripts/fixtures/` holds packets and reports.

`tests/scripts/toolkit_paths.py`: `TREE_CLAUDE_DIR = Path(__file__).resolve().parents[2] / "claude" / ".claude"`; `CLAUDE_DIR = Path(os.environ.get("TOOLKIT_CLAUDE_DIR") or TREE_CLAUDE_DIR)`; `REPO_ROOT`; `SCRIPTS_DIR = CLAUDE_DIR/"scripts"`; `CODE_DIR`, `REVIEW_DIR`, `TELEMETRY_DIR`, `LIB_DIR`, `TOOLS_DIR`, `GATES_DIR` as subfolders (lines 13-27). `script_in(scripts_root, name)` globs `*/name` (66-71). Tests add `LIB_DIR` and `REVIEW_DIR` to `sys.path` and import bare module names. Other: `first_python_that_starts`, `PRE_314_PYTHON`, `REAL_PLANS_ENABLED`, `CODER_GATE_LIB_MODULES`, ledger guard (`LEDGER_GUARD_*`).

### 7. `plan_check.py owner` and criteria owner

`plan_check.py` `print_owner(path_args)` (`S/code/plan_check.py:75-83`): exactly one arg else `sys.exit(USAGE)`; `plan_format.plan_criteria_owner(pathlib.Path(arg))`; `PlanFormatError` prints the message and exits 1; success prints `json.dumps({"owner","ticket","source","rule"})`. Dispatched at `main` (`args[0] == "owner"`, 90).

`plan_format.plan_criteria_owner(plan_path)` (`S/lib/plan_format.py:1588-1599`): `ticket_beside(plan_path)` (1559: `00-ticket.md` in the plan's folder, else a single `*-00-ticket.md`; several raise `PlanFormatError`). With a ticket: `criteria_owner(ticket)`. With none: `plan` if `plan_author_criteria_missing` is empty (the plan is an existing file named `plan.md` and `acceptance-criteria.md` exists in its folder), else `user`; `ticket: None`.

`criteria_owner(ticket_path)` (1527-1552) in order:
1. Ticket text frontmatter `type: "QueueItem"` (`is_queue_item_text`, `QUEUE_ITEM_TYPE`): author from its own `generated.by` (`queue_text_author`), owner from `author_owner`; `source` None.
2. `queue_source_line(lines)` (1450-1468) finds the first `Source:` line whose value starts with the queue folder. Accepted spellings: `Source: ~/agent-evals/queue/x.md`, with leading `- `, markdown marks `*_` and backticks around the label and the path word (`SOURCE_LINE = ^(?:-\s+)?source:\s*(.*)$` after `MARKDOWN_MARKS` stripped, 1439), and the home-folder spelling `<home>/agent-evals/queue/...` normalized to `~` (`home_queue_prefix`, 1446). Marks are stripped from the path word's ends only (underscores inside stay). A `Source:` outside the queue folder is skipped and never changes the owner (test `test_a_non_queue_source_line_before_the_queue_one_is_skipped`, `tests/scripts/test_plan_format.py:627`). The value must match `QUEUE_SOURCE_FORM = ^~/agent-evals/queue/[a-z0-9-]+\.md(?: .*)?$` (1438) or `PlanFormatError`; the file must exist; its frontmatter `generated` must be a JSON object with non-empty `by` (`queue_item_author` 1471, `queue_text_author` 1486).
3. `author_owner(author)` (1515): `human:` prefix (`HUMAN_AUTHOR_PREFIX`) maps to `user`; any other author maps to `session`.
4. No queue source: `ticket_criteria` (1336) raising `NoCriteriaHeadingError` (class at 98) maps to `plan`; otherwise `user`. Criteria headings (`AC_HEADING`, 1148): `##`/`###` + `Acceptance`, `Acceptance criteria`, `Requirements`, or `Done when`, optional colon, case-insensitive; a loose near-match heading raises `PlanFormatError`.

Owner constants: `CRITERIA_OWNER_USER/PLAN/SESSION` (1425-1427), rule texts `CRITERIA_OWNER_RULES` (1428-1436). Ruling side: `DECIDE_BY_NOTE` (`plan_format.py:880-886`) and `PLAN_CHECK_OWNER_COMMAND` (877). Tests: `tests/scripts/test_plan_check.py:45-138`, `test_plan_format.py:515-633`, `test_verify_branch_script.py:352,375` (queue Source in verify-prep).

### 8. `eng-spec/phases/1-ticket.md`

File is 18 lines (`claude/.claude/skills/eng-spec/phases/1-ticket.md`):
1. Get the ticket, in order: a `/pull-ticket` result in the thread; a ticket/spec file path in the argument (read it); a Jira key/URL (fetch it yourself per `~/.claude/skills/_shared/jira-ticket.md`). Required-ticket caller with no key: ask the user; Jira MCP down: say so and stop.
2. Check for an existing spec: Glob `docs/plans/**/spec.md`; if one matches, read it and ask "update it or start fresh?".
3. Open the task directory `docs/plans/<slug>/`: a Jira key always goes in the slug; with no key, kebab-case area plus date (never the change). `Write` the ticket verbatim to `00-ticket.md` per the persistence rule in `jira-ticket.md`. "When the ticket is a file under `~/agent-evals/queue/`, the first line under the title is `Source: ~/agent-evals/queue/<slug>.md`."

Helper scripts called: none in this file. The persistence rule is `skills/_shared/jira-ticket.md:25-29` ("Write raw fields only, verbatim"; comments under `## Comments`). The only checker of the `Source:` line is `plan_format.criteria_owner` / `plan_check.py owner` (Q7).

### 9. Queue item location and readers

- Items: `~/agent-evals/queue/<slug>.md` (1377 files now incl. `index.md`/`log.md` reserved). Frontmatter keys as `key: <JSON value>` lines: `type: "QueueItem"`, `title`, `description`, `generated: {"by": "...", "at": "..."}`, `kind`, `status`, `blocked_by`, `source`, `components`, `closed` (example `queue/accepted-claude-md-approval-ask-reverts-the-file.md:1-12`; sections `## Context`, `## Done when`).
- `bin/build_queue.py` (954 lines): docstring (1-86) lists keys (kind: method, bench, live-edit, chore; status: queued, running, blocked, done, dropped; rank; `source` repo-relative path) and subcommands `new`, `prior`, `set`, `claim`, `unclaim`, `claimed`, `build` (no subcommand builds `QUEUE.md` and `queue/index.md`; `--check`). `QUEUE_DIR` imported at line 123; `SOURCE_PATHS` 142; item loading around 215-250 via `git_remote_commit.tracked_names_at_top(root, QUEUE_DIR)`; `new` at 398; `set` at 577; `main` at 784.
- Dotfiles toolkit references to a queue item path:
  - `S/lib/plan_format.py:1437-1491` (`QUEUE_SOURCE_PREFIX`, `QUEUE_SOURCE_FORM`, `SOURCE_LINE`, `home_queue_prefix`, `queue_source_line`, `queue_item_author`, `queue_text_author`, `is_queue_item_text`).
  - `claude/.claude/skills/eng-spec/phases/1-ticket.md:17-18`.
  - Verify-prep reads the ticket Source through plan_format (tests `tests/scripts/test_verify_prep_queue_ticket.py`, `test_verify_branch_script.py:352,375`).
  - `tests/scripts/fixtures/script_run_quoted_args.sh:1` (a `build_queue.py new` command).
  - Global CLAUDE.md "Bugs and Inefficiencies" runs `python3 ~/agent-evals/bin/build_queue.py new`.
  - Searched `claude/` and `tests/scripts/` with `rg "agent-evals/queue|QUEUE_SOURCE|queue_source|build_queue"`; no other script under `claude/.claude/scripts` named a queue item path.

### 10. Rule-meter harness

- `bin/rule_meter.py` (2864 lines). Header docstring (1-40): a cell is a rule x prompt level x arm; builds a bench tree from the `ticketsim` fixture, appends the global CLAUDE.md to the tree's project CLAUDE.md (arm off removes the rule's text), runs `claude -p` on the task, grades tool calls and tree with a detector. Outcomes: COMPLIED, VIOLATED, NO_TEST, NO_CHANGE, ERROR. Commands: `run --rule --level --arm [--run] [--dry-run]`, `run-all [--runs N] [--level L] [--dry-run]`, `summary`.
- Constants: `LEVELS = ("supportive", "neutral", "competing")` (87), `ARMS = ("on", "off")` (88), `CHECK_SOURCES = HERE / "rule_meter_checks"` (161), results at `~/dev/evals/rulemeter1/runs/results.jsonl`.
- Scenarios: `bin/rule_meter_scenarios.json` (1974 lines; a JSON dict, 113 entries keyed by rule id such as `C`, `G`, `AA`, `TR01`, `CF01`, `research-subagent-per-repo`). Keys by count: `name`, `setup`, `detector`, `task`, `suffix` (all 113); `rule_text` (105), `rule_source` (104), `toolkit_root` (99), `retired` (91), `note` (84), `agent` (83), `plant` (73), `model` (51), `family` (21), `split` (10), `rule_file` (8). 22 scenarios are not retired. `suffix` is `{supportive, neutral, competing}` text appended to the task (example scenario `C`: `detector: "no_nested_call_args"`). `setup` is null for 108; others `untracked_script`, `review_stop_two_asks`, `review_stop_two_asks_turn`, `three_toolkits`, `four_web_apps`.
- Arms: `on` = the rule source whole; `off` = `remove_once(source_text, scenario["rule_text"])` (`rule_source_for_arm`, `bin/rule_meter.py:1644-1653`; a missing fragment exits with a message). `rule_source` (a toolkit file relative to the scenario's toolkit root) with `agent` makes the session run as that agent with its skills copied into the tree's `.claude/` (docstring 31-37).
- Detectors: `grade(...)` dispatch by `scenario["detector"]` starting at `bin/rule_meter.py:1479`: stack detectors (`STACK_RED_DETECTORS`, `STACK_FILES`), coder5 (`CODER5_FILES`, `red_test_first`), named ones (`no_unstage`, `changed_tests_only`, `no_blockquote`, `domain_naming`, `code_paragraphs`, `no_nested_call_args`, `max_nesting`, `readability_first`), `RECORD_DETECTORS`, `rule_meter_fixture.DETECTORS`, `rule_meter_verifier.DETECTORS`, and others; detectors are pure functions over tool calls and a tree-state dict (section header at 278). Most common detector names: `keeps_user_in_this_pane` (5), `red_test_first` (4), `react_red_test_first` (4), `decision_blocks_marked` (4).
- Hidden checks: `bin/rule_meter_checks/` holds 12 files: `async_panel_states.mts`, `async_view_states.mts`, `branch_has_failing_test.py`, `incidental_owner_filters.py`, `keep_behavior.mts`, `keep_date.mts`, `keep_quantity.mts`, `second_owner_mutation.py`, `stale_docs.mts`, `sweep_defaults.mts`, `sweep_owner_check.mts`, `weak_fix_test.mts`.
- `toolkit_root`: optional scenario field, a path with `~` allowed. `toolkit_home(scenario)` (`bin/rule_meter.py:1655-1661`) returns `Path(scenario["toolkit_root"]).expanduser()` else `CLAUDE_HOME` (`~/.claude`). `rule_source_path` (1664) = `toolkit_home / rule_source` else global CLAUDE.md. `check_toolkit_root(rule, scenario)` (1681-1687) exits with "toolkit_root ... does not exist; re-point it or mark it retired" when the directory is missing; `check_rule_texts` (1690-1698) runs it for each non-retired scenario. Observed values: dotfiles worktrees (`~/dotfiles-coder-rules/claude/.claude`, `/home/brandon/dotfiles-code-skill-nov22/claude/.claude` for `CF01`-`CF07`, `/home/brandon/dotfiles-toolkit-prose-nov22/claude/.claude` for `ES01W`/`ES02W`), `/home/brandon/dotfiles/claude/.claude` (`L`, `RF01`, `RF05`, `RF03`), and copies under `~/dev/evals/rulemeter*/...`.

### 11. `docs/changes/` convention

Layout: `docs/changes/notes/<YYYY-MM-DD>-<slug>.md` (1104 notes, e.g. `notes/2026-11-22-verify-prep-keeps-a-branch-review-current-when.md`) plus six generated pages: `index.md`, `what-worked.md`, `ruled-out.md`, `changelog.md`, `in-progress.md`, `fixes-by-script.md` (each begins `<!-- generated by bin/build_changes.py from the change files; edit those, not this page -->`). Builder and validator: `~/agent-evals/bin/build_changes.py` (docstring 1-100), page rendering `bin/change_pages.py`.

Required frontmatter keys (`key: <JSON value>` lines): `type: "Change"`, `change_type`, `title`, `description`, `generated {by, at}` (ISO datetime with offset; first 10 characters equal the stem date), `seq` (int >= 1, position among same-date changes), `components` (distinct ids like `script/verify-prep`; may be empty), `evidence` (at least one kind), `watches` (ids from `edit-watches.json`; may be empty). `change_type` in `CHANGE_TYPES = ("added","changed","removed","fixed","security","deprecated")` (`build_changes.py:175`).
Optional: `kind`, `test`, `asked`, `proof`, `unmeasured`, `overlap`, `regression` (only on `fixed`), `reverts`, `impact`. `kind` is required for stems dated 2026-10-24 or later (`KIND_REQUIRED_FROM`); from 2026-10-25 (`PROOF_REQUIRED_FROM`) kind is one of `fix` (needs `test` as `path::name`), `user-rule` (needs `asked`: `<YYYY-MM-DD>: <paraphrase>`, no quote marks), `structured` or `open` (need `proof`: findings stems, run floors 8 and 32); `behavior` is refused; a behavior-kind note needs `watches` or `unmeasured`.
Body: level-2 headings `Change`, `Evidence`, `Result`, `Watch`, `Back-out`, in that order, each with text (a dash if nothing).
Validation: `build_changes.py` parses and validates with `build_findings` helpers, collects every problem, exits 1, writes nothing; `--check` compares generated pages with a fresh build; a privacy guard refuses built pages that match `WORK_TERMS`; `new` writes an unfilled stub at the next `seq` and rebuilds nothing (untracked stubs are left out and named). Bundle root defaults to `docs/changes` of the dotfiles checkout holding the cwd.

## Code References

- `S/review/review_loop_ruled.py:52-56` - `approval_only_paths`.
- `S/review/review_loop_ruled.py:366-393` - `ask_for_approval_only_edits` (keep / revert / ask).
- `S/review/review_loop_ruled.py:460-485` - `revert_approval_edit`.
- `S/review/review_loop_ruled.py:502-522` - `snapshot_approval_blobs`.
- `S/review/review_loop_ruled.py:596-603` - `is_approval_ruling`.
- `S/review/review_loop_script.py:573-591` - pass snapshots, put-back, approval handling order.
- `S/review/review_loop_partial_fix.py:205-213` - same handling on a dead pass.
- `S/lib/format_files.py:25` - `PROMPT_MARKDOWN_NAMES`.
- `S/lib/protected_lines.py:55` - `restore_protected_lines`.
- `S/lib/signoff_lines.py:161,176` - `signoff_scope_indexes`, `signoff_lines`.
- `S/review/review_loop_signoffs.py:264,301,345` - `SignoffSnapshot`, `SignoffRuns`, `undo_signoff_pass`.
- `S/review/review_loop_put_back.py:10,25` - `ProtectedPutBack`, `put_back_lines`.
- `S/lib/standing_rulings.py:16-20,27,46,60` - form, reader functions.
- `S/lib/ruled_change_text.py:98-101,114,119,138` - clauses, marker, `changed_text`, `ruled_note`, `is_no_code_ruling`.
- `S/lib/ask_outcome_words.py:160-188` - outcome words, relay flag names.
- `S/lib/plan_format.py:61-62,88,861-868,904-912` - deviations heading, session owner string, `ruling_owner`, `ruling_deviation`.
- `S/lib/plan_format.py:1336,1425-1552,1588-1599` - criteria, owner constants, `queue_source_line`, `criteria_owner`, `plan_criteria_owner`.
- `S/code/plan_check.py:75-90` - `owner` subcommand.
- `claude/.claude/skills/eng-spec/phases/1-ticket.md:12-18` - ticket snapshot and Source line.
- `tests/scripts/toolkit_paths.py:13-27,66-71` - path constants, `script_in`.
- `~/agent-evals/bin/rule_meter.py:1655-1698` - `toolkit_home`, `check_toolkit_root`, `check_rule_texts`.
- `~/agent-evals/bin/build_changes.py:39-100,175-190` - change-note grammar and constants.
- `~/agent-evals/bin/build_queue.py:1-86,784` - queue item grammar, subcommands, `main`.

## Patterns Found

- Mixin-on-`LoopRun`: each review-loop concern is a class of methods (`RuledFindings`, `SignoffRuns`, `CommentRemovalRuns`) reading host attributes (`repo`, `plan`, `asks`, `adopted`, `session_ruled`...); the host-attribute list is stated in the module docstring (`review_loop_ruled.py:3-4`).
- Snapshot before the coder pass, compare after: approval blobs, sign-off lines and comment lines are each captured before `coder_call` and restored after.
- Fail closed on unknown pre-pass content (`UNKNOWN_BASE`), keep the edit and ask.
- Rulings recorded with who and when and never the user's words: standing rulings forbid quote marks (`standing_rulings.py:9,19`); `ask_outcome_words.RETIRED_QUOTE_FLAG`.
- One-grammar-with-loud-failure: `PlanFormatError` messages start `name:line:`; `standing_rulings_in` and `queue_item_author` follow it.
- Facts with a single owner module, standard-library-only for modules imported by gates (`ruled_change_text`, `ask_outcome_words`, `stop_file_names`).
- Frontmatter-as-JSON-lines files across agent-evals (queue items, change notes, findings) validated by a builder that collects all problems and writes nothing on any.
- `NamedTuple` records for loop data: `Unapplied`, `SignoffSnapshot`, `ProtectedPutBack`.

## Dormant scaffolding (on the questioned surfaces)

- `ask_outcome_words.APPLIED` and `HELD` constants (lines 172, 175) are defined there; I did not trace their consumers beyond that file.
- `signoff_lines.DISAGREEMENT_LINE`, `BULLET_LINE` are used only inside `signoff_lines.py`.
- `protected_lines.in_span_with` (47): searched only the `S/lib` and `S/review` definitions and the loop files read here; `review_loop_comment_removal` uses `changed_stretches`, `consecutive_runs`, `entries_missing`; I did not find a caller of `in_span_with` in the files read (not exhaustively searched).
- `standing_rulings.ruling_label` (91): no caller in the files read (not exhaustively searched).
- `scenarios`: 91 of 113 rule-meter scenarios carry `retired`; 22 are live.

## Reuse Inventory

- `approval_only_paths(changed) -> list[str]` - `S/review/review_loop_ruled.py:52` - paths whose basename is an approval-only name.
- `approval_ask_text(path) -> str` - `review_loop_ruled.py:59` - text of the revert ask.
- `no_code_numbers(findings) -> list[int]` - `review_loop_ruled.py:65`.
- `rejected_ask_records(session_id, repo) -> list` - `review_loop_ruled.py:70`.
- `names_changed_path(finding_path, changed_path, repo) -> bool` - `review_loop_ruled.py:78`.
- `ruling_line(finding) -> str` - `review_loop_ruled.py:84`.
- `broken_ruling_finding(ruled, other_paths, path, every_finding_ruled, repo)` - `review_loop_ruled.py:90`.
- `not_applied_why`, `unapplied_adopted`, `withheld_adopted`, `prior_issue_entries`, `adopted_rulings` - `review_loop_ruled.py:121,134,150,163,114`.
- `entries_missing(before, after)`, `changed_stretches(before, after)`, `consecutive_runs(entries)`, `in_span_with(number, spans, named_lines)`, `restore_protected_lines(before, after, numbers, whole_stretch, may_replace)` - `S/lib/protected_lines.py:10,24,36,47,55`.
- `signoff_lines(text, name="") -> [(int, str)]`, `signoff_scope_indexes(name, lines) -> set`, `is_signoff_marker(line)`, `entry_start(lines, index)`, `continuation_end(lines, start)` - `S/lib/signoff_lines.py:176,161,127,134,144`.
- `is_decision_log(path)`, `recorded_signoff_lines(path, text)`, `in_signoff_scope`, `signoff_entry_line`, `finding_hits_signoff`, `signoff_ask`, `snapshot_signoffs(repo, extra_paths)`, `lost_lines`, `objection_text` - `S/review/review_loop_signoffs.py:210,216,221,230,242,257,271,289,295`.
- `put_back_lines(repo, path, before_text, current, numbers, whole_stretch, may_replace)`, `fully_put_back_paths(put_back)` - `S/review/review_loop_put_back.py:25,33`.
- `standing_rulings_in(lines, name, indexes)`, `standing_rulings(plan_path)`, `reword_ruling(plan_path)`, `impact_rewords_criterion(text)`, `ruling_label(ruling)` - `S/lib/standing_rulings.py:27,46,60,68,91`.
- `changed_text(base, note, ruler_clause)`, `ruled_note(text)`, `is_no_code_ruling(note)`, `is_no_code_finding(text)`, `asks_for_test_edit(clause)` - `S/lib/ruled_change_text.py:114,119,138,150,128`.
- `rule_command(count, by_user=False)`, `user_only_numbers(asks)`, `user_only_reason(item)`, `rule_instruction(asks)` - `S/lib/ask_outcome_words.py:191,199,204,212`.
- `ruling_owner(repo_dir, by)`, `ruling_deviation(phase, decision, owner, ruled_at, ruling_words, disagreement)`, `ruled_at_now()`, `is_ruling_by(by)`, `append_deviation(...)` - `S/lib/plan_format.py:864,904,897 area,873 area`; `append_deviation` called at `S/review/review_fix_plan_impacts.py:120`.
- `criteria_owner(ticket_path)`, `plan_criteria_owner(plan_path)`, `queue_source_line(lines)`, `queue_item_author(name, number, value)`, `queue_text_author(where, subject, text)`, `is_queue_item_text(text)`, `author_owner(author)`, `owner_record(...)`, `ticket_beside(plan_path)`, `plan_author_criteria_missing(plan_path)`, `ticket_criteria(text, name)`, `home_queue_prefix()` - `S/lib/plan_format.py:1527,1588,1450,1471,1486,1503 area,1515,1522,1559,1580 area,1336,1446`.
- `script_utils.frontmatter_value(text, key)`, `frontmatter_line_number(text, key)`, `heading_section_indexes(lines, heading)`, `write_text_atomically`, `content_changed_since`, `restore_blob`, `index_entry`, `restore_index_entry`, `head_commit`, `blob_at_commit`, `repo_file_paths`, `work_tree_blob`, `matches_head` - used by the files above; defined in `S/lib/script_utils.py` (names as called at `review_loop_ruled.py:472-522`, `plan_format.py:1495-1530`).
- Tests: `toolkit_paths.LIB_DIR`, `REVIEW_DIR`, `script_in(scripts_root, name)` (`tests/scripts/toolkit_paths.py`); `ruled_finding`, `Host`, `approval_host` (`tests/scripts/test_review_loop_ruled.py:38,47,67`); `ReviewLoopHarness` (`tests/scripts/test_review_loop_script.py:617`).
- agent-evals: `rule_meter.toolkit_home(scenario)`, `rule_source_path(scenario)`, `read_rule_source`, `rule_source_for_arm(source_text, scenario, arm, source_path)`, `check_toolkit_root`, `check_rule_texts(scenarios)`, `load_scenarios()` (1628) - `bin/rule_meter.py`; `build_changes.py` (`new`, build, `--check`), `build_queue.py` (`new`, `prior`, `set`, `claim`, `unclaim`, `claimed`, build `--check`).

Note on citations: line numbers for lines within a few places marked "area" (`plan_format.py` helpers `append_deviation`, `plan_author_criteria_missing` and `ticket_criteria` neighbors) are approximate; the functions are named, find them with `rg -n "def append_deviation" S/lib/plan_format.py`.
