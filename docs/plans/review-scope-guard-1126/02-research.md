---
date: 2026-11-26
git_commit: f66808dfa4dccc77a8e608a6edf2ec88dcf42180
branch: fix/review-scope-guard-outside
topic: review loop base selection, scope guard put-back, sibling guards, asks, plan format, fix state and tests
tags: [review-loop, scope-guard, merge-free-base, tests]
status: complete
---

# Research: review loop base selection, scope guard put-back, sibling guards, asks, plan format, fix state and tests

Paths are under `claude/.claude/scripts/` (called TK) unless they start with `tests/`.

## Findings

### 1. `lib/merge_free_base.py`: base computation and callers

- `resolve_base(repo, base, name=None)` (TK/lib/merge_free_base.py:55). It runs `git merge-base --is-ancestor <base> HEAD`. Exit 0 returns `BaseResolution(name, base, base)` (:63). Exit 1 runs `git merge-base HEAD <base>`, and the found commit becomes `used` (:74). No merge base raises `NoMergeBaseError` (:67). Any other git failure raises `MergeBaseGitError`.
- `BaseResolution(given, commit, used)` is a NamedTuple (:37). `given_if_moved()` returns `given` only when `used != commit` (:48).
- `merge_free_base(repo, base)` (:128). For each first-parent merge in `base..HEAD`, oldest first (`merge_commits`, :80), it folds every merged-in parent (`merged_in_parents`, :91) into the running base via `fold_parent` (:103). `fold_parent` runs `git merge-tree --write-tree --name-only --allow-unrelated-histories` and `git commit-tree`. It returns `base` unchanged when there are no merges. A conflict raises `MergeConflictError` (:19), which carries `.merge`.
- Callers (non-test):
  - `review/review_launch.py:194` `resolved_base(repo, base)` rev-parses `<base>^{commit}` and calls `resolve_base(repo, commit, base)` (:201). It does NOT call `merge_free_base`. In `main`, `base = base_resolution.used` (:641) and `given_base = base_resolution.given_if_moved()` (:678). Both go into the prompt header as `base:` and `given-base:` (`header_pairs`, :290-301).
  - `code/code_review_start.py:416` `diff_base(repo, base_commit, base)` calls `resolve_base(...)` and then `merge_free_base(repo, resolved.used)` (:422-423). The result is `ReviewScope.review_base` (:452-456). `ReviewScope.given_base` is `base if review_base != base_commit else None` (:456). `review_prompt` writes `BASE_KEY: <review_base>` and `GIVEN_BASE_KEY` into the header (:467-470).
  - `code/phase_start.py:211` `own_tick_base` calls `merge_free_base(repo, kept_head)` for the phase-tick comparison only. On error it prints to stderr and falls back to `kept_head` (:214-217).
- Tests: tests/scripts/test_merge_free_base.py (`MergeFreeBaseTest` :27, `ResolveBaseTest` :156). `tests/scripts/test_review_launch.py:335-403` covers `resolved_base` and the `base:` / `given-base:` header lines.

### 2. How the review loop chooses its diff base

- The loop does not compute a base itself. `review/review_loop_main.py:157-158` reads `loop.review_base = header.get(BASE_KEY, "")` and `loop.given_base = header.get(GIVEN_BASE_KEY, "")` from the prompt-file header. The attribute defaults are `""`, meaning HEAD (review/review_loop_script.py:401-402).
- Header writers: `review_launch.py` (:640-679) and `code_review_start.py` (:467-470). The header key constants are `BASE_KEY = "base"` and `GIVEN_BASE_KEY = "given-base"` (review/review_loop_prompt_file.py:47-48).
- The launcher's `relaunch_args` records the raw `--base` as typed (`options.base`, review_launch.py:373-374), not the resolved commit. Both launcher paths store it that way.
- Uses of `self.review_base`:
  - `review_scope()` calls `review_files(self.repo, self.review_base, self.only_files)` (review_loop_script.py:414-415). `review_files` (review/review_loop_plan.py:142) calls `base_scope(repo, base)` when a base is set, else `scope(repo)`.
  - `base_scope` (review_loop_plan.py:32) runs `git diff --numstat/--name-status -z --no-renames <base>` and adds the untracked files from `scope`.
  - `review_added_ranges` (review_loop_script.py:574) and `nearest_functions_text` (:448).
  - `full_check_gate.py:173`: `base = self.review_base or full_check.DEFAULT_DIFF_BASE`.
  - The prompt text `Review every change since {base} ... git diff {base}` (review_loop_prompt_file.py:259-267).
  - The packet fields `base_used` and `given_base` (review_loop_script.py:883-884; review_loop_packet.py:101-102). `handback.py:685-687` prints "Review base: <given> is no ancestor of HEAD or has merges on the branch; reviewed since <base_used>".
- With `review_base == ""`: `keep_coder_commit_in_scope` (review/review_loop_pass_checks.py:34-42) sets `self.review_base = self.change.start` after a coder commit. `ChangeUnderReview.start` is `head_commit(repo)` at loop start (review_loop_plan.py:96).
- Within the loop, nothing calls `merge_free_base` or `resolve_base`. No test or caller outside `review_launch.py` and `code_review_start.py` computes the loop base.

### 3. `review/review_loop_scope_guard.py`: scope, put-back, change discovery, state

Entry point: `guard_pass(repo, out, role, allowed, has_own_guard, finding_texts, gate_passes)` (:318). It is called at review/review_loop_script.py:609.

- **Which files are in scope** (`PassScope.holds(path)`, :34-39). A path is in scope when any of these holds:
  - It is in `allowed`.
  - `has_own_guard(path)` is true.
  - `script_utils.texts_name_repo_file(finding_texts, path, root, repo_files)` is true. That means a finding names the full path, `./path`, or a unique trailing part containing `/` or `.`.
- `allowed` comes from `LoopRun.pass_scope(files_in_scope)` (review_loop_script.py:652-659). It is `{*files_in_scope, *files_touched, *held_files, *ruled_out, *later_phase_files}`. `files_in_scope = diff_files (self.review_scope()) + finding_paths` (:600-601). `review_scope()` is the base diff from section 2, with the plan folder and held/ruled-out files removed (:414-419).
- `has_own_guard` is `own_guard_test(signoffs)`, built from the sign-off snapshot (:610).
- **How it learns what the pass changed.** It takes no pass report.
  - At guard start: `worktree_snapshot.status_codes(root, strict=True)` lists the dirty paths, filtered to those not held by scope (:324). It also records:
    - `index_entries` of those paths (:325)
    - `head = head_commit_or_unborn` (:326)
    - `dirty_before = paths_differing_from_head(root, head)` (:327)
    - a file backup of the dirty out-of-scope paths (:328)
  - After the pass, `undo()` compares the live tree to that start state:
    - Dirty-before files: `file_backup.saved_paths_that_differ(backup)` (`put_back_dirty_files`, :117-123).
    - Dirty-before index entries: `index_entries` now versus before (:125-141).
    - Clean-before files: `changed_clean_files` is `paths_differing_from_head(repo, head, "--diff-filter=MDT")` minus `dirty_before`, filtered by `not scope.holds` (:152-156). The comparison is against the pass-start HEAD commit, not against the review base.
  - Files the pass created stay (module docstring). Files it committed are put back in the work tree and index, but HEAD keeps the commit.
- **Put-back mechanics.**
  - `keep_bytes_of` copies the bytes it will overwrite to `put_back_dir` (:106-115).
  - `put_back_clean_files` runs `git --literal-pathspecs restore --source=<head> --staged --worktree -- paths` (:158-174).
  - `put_back_everything` runs the three steps in order (:176-183).
- **Judging**, `keep_needed_files` (:221-253). It calls `gate_passes()` (`StrayFiles.stray_gate_passes`, review/review_loop_stray_files.py:20):
  - Gate passes without the strays: `stray_blocker` is set ("the gate passes without it").
  - Gate result is None: `stray_blocker` is set ("no gate ran").
  - Gate fails without but passes with: `needed_strays` judges each stray alone. Needed ones stay (`keep_files_as_needed`, :212-228), noted in `SCOPE_FAULTS`. The rest set `stray_blocker`.
- **State.**
  - Per-guard instance attributes: `put_back_paths`, `unkept_paths`, `replaced_blobs`, `saved_paths`, `deleted_paths`, `restored_strays`, `stray_blocker`, `failed`, `current_step`, `unsaved_hashes`, `changed_unsaved`.
  - Module global `SCOPE_FAULTS` (list, :19), read by `review_loop_coder.coder_fault_notes()` (review_loop_coder.py:22-27).
  - On disk: `<out>/pass-backup/<role>/out-of-scope/` (backup) and `<out>/pass-backup/<role>/put-back/<N>/` (bytes overwritten; `script_utils.next_numbered_dir`). `BACKUP_FOLDER = "pass-backup"` is imported from review_loop_ruled_out.py:21. The backup is discarded when no step failed (`note_faults`, :314-316).
- **Loop wiring.**
  - `coder_call(..., scope_guard=...)` runs `scope_guard.undo(judge)` via `undo_pass` (review_loop_coder.py:179-186).
  - `LoopRun.repair` then calls `stop_on_stray_files` (review_loop_script.py:648; review_loop_stray_files.py:37-44). This raises `StrayFileError(scope_guard.stray_blocker)`.
  - Before raising, it runs `files_touched.update(result.changed)` and `keep_unreverted_open`.
  - `review_loop_main.py:221-223` catches it as `loop.stop("critical-blocker", [str(error)])`.
- `has_own_guard`, `allowed` and `scope.holds` never read `review_base` directly. `files_in_scope` carries the base diff in via `review_scope()`.

### 4. Path representation and comparison in the scope guard

- Paths are plain `str`, repo-root-relative, as git prints them. Sources:
  - `git status --porcelain -z` (worktree_snapshot.py:24-48)
  - `git diff --name-only -z --no-renames` (scope_guard:51-53)
  - `git ls-files --cached --others --exclude-standard -z` (`script_utils.repo_file_paths_or_raise`, :602)
- `PassScope.allowed` and `repo_files` are `frozenset[str]`. `put_back_paths`, `saved_paths`, `deleted_paths` and `unkept_paths` are `set[str]`. `index_entries` is `{path: IndexEntry(mode, blob) | None}` (script_utils.py:437, :440).
- Comparison is exact string equality / set membership (`path in self.allowed`, `set & set`, `entries_now[path] != entry`).
- Only finding texts get fuzzy matching, in `script_utils.texts_name_repo_file` (:1035), which calls:
  - `texts_relative_to` (:1000) strips the `root/` prefix and a leading `./`.
  - `names_path(..., as_token=True)` (:988) uses `PATH_TOKEN_START` / `PATH_TOKEN_END` (:985-986).
  - `texts_name_path_by_suffix` (:1012) uses `path_has_tail` (:1007), a trailing part with `/` or `.` that only one known path ends with.
- Paths from the base diff and finding paths are normalized elsewhere before they reach `allowed`: `review_loop_held.held_path_in_repo(finding.path, repo)` (review_loop_script.py:598-599).
- Git calls use `--literal-pathspecs` (`index_entries` :446; `put_back_clean_files` :168; `restore_index_entry` :474).
- `--no-renames` is used so a rename lists both paths (scope_guard:45-47 docstring). `status_entries` uses `--find-renames` and a separate `origins` map (worktree_snapshot.py:24-48). Only the code map (`status_codes`) reaches the scope guard.

### 5. Stop packet and blocker lines

- The loop outcome is assembled at `review_loop_script.py:~878-895` (`outcome()`):
  - `blockers`: `self.remaining` when status is in `handback.BLOCKER_STATUSES`, else `[]`.
  - `base_used`: `self.review_base`.
  - `given_base`: `self.given_base`.
- `review_loop_packet.py:packet_message` (:~66) renders the JSON packet. Fields about files:
  - `files_touched: outcome["files_touched"]` (:89)
  - `check_changed`, `check_rewrote_edited`, `check_created` (:107)
  - `tool_fault` (:107)
  - `left_alone`
- `EMPTY_OUTCOME` (:115-127) holds every key empty. `crash_outcome` (:130-136) fills `files_touched` from `progress["files_touched"]` (sorted) and `tool_fault` with `reason + coder_fault_notes()`.
- Stray-file stop: `StrayFileError` message equals `ScopeGuard.stray_blocker`, built by `stray_blocker_text` (scope_guard:181-198). The text contains:
  - the role
  - the stray paths
  - the reason
  - "the loop put it/them back"
  - "and kept the pass's bytes in <put_back_dir>"
  - "; the pass deleted <paths>"
  The status is `critical-blocker` with `blockers = [message]` (review_loop_main.py:221-223).
- What the packet records about changed files in a stray stop: `files_touched.update(result.changed)` runs first (review_loop_stray_files.py:43). Put-back files are not in `result.changed`, so a put-back file stays out of `files_touched` (test at test_review_loop_scope_guard.py:209-224 asserts `assertNotIn("notes.py", packet["files_touched"])` for the non-stop case; the stop case asserts `app.py` in `files_touched`, :1173-1188). `tool_fault` carries the `SCOPE_FAULTS` notes, including the put-back folder path.
- `review/review_blocker_text.py` (33 lines): `blocker_text(text)` returns one line via `script_utils.one_line`. Beyond `FULL_TEXT_LIMIT = 2000` chars it truncates and appends `[full text: <path>]`. `full_text_file(text)` writes `<review-fix dir>/blocker-text/<sha256[:12]>.txt` via `write_text_atomically`. The only caller is `review_fix.py:515` (blockers) and :523 (plan impact). The loop does not call it.
- `handback.py`:
  - `LIST_KEYS` includes `files_touched` (:82). The string keys include `tool_fault`, `base_used` and `given_base` (:73-79).
  - `fixed_paths(packet)` (:587) resolves `fixed[]` names against `files_touched` through `touched_paths_named` (:579) and `is_same_file`.
  - Rendering lines "Review base: ..." (:685-687) and "Tool fault: ..." (:691-692).

### 6. Sibling guards and their relation to the scope guard

- `review_loop_ruled_out.py`:
  - `begin_pass` (:112) backs up `ruled_out` files (`pass-backup/<role>/ruled-out`) and the diff files that no finding asks to delete (`.../diff`).
  - `PassGuard.undo` (:~87):
    - `put_back_ruled_out` (`file_backup.put_back_all`) restores or removes ruled-out files and leaves directories created at ruled-out paths.
    - `file_backup.restore_missing` restores diff files the pass deleted with no naming finding.
    - Notes go to `RULED_OUT_FAULTS` (:25).
  - `names_deletion` (:~61) matches `delet|remov|mov|renam` plus a path token in the finding text.
  - `BACKUP_FOLDER = "pass-backup"` (:21) is imported by the scope guard.
- Relation, in `review_loop_coder.undo_pass` (:179-186): `pass_guard.undo()` runs first, then `scope_guard.undo(judge)`. If the pass guard fails, `undo_scope_after_failure` runs the scope undo with `judge=False` and joins both errors (`GuardUndoError`). Ruled-out files are in the scope guard's `allowed` (`pass_scope` includes `*self.ruled_out`), so the scope guard leaves them to the ruled-out guard. Held files and later-phase files are also in `allowed`.
- `review_loop_untracked.py`:
  - `begin(repo, out, deletable)` copies the guarded untracked files (`untracked_set - LOOP_WRITTEN - deletable`). `CallGuard.restore` puts back removed ones (`file_backup.restore_missing`).
  - `record_loop_written` adds new untracked files to `LOOP_WRITTEN` and `fix_coder_written`.
  - Notes go to `UNTRACKED_FAULTS`. It wraps every model call.
  - `ruled_out.begin_pass` excludes the files `guarded_untracked` already covers, so one deletion makes one note (:~127-128).
- `review_loop_signoffs.py`:
  - `snapshot_signoffs(repo, extra_paths)` records the text and sign-off lines (`SignoffSnapshot(texts, lines)`) of the plan-folder markdown and extra decision logs.
  - `undo_signoff_pass(snapshot, findings, skip)` (:~195) uses `lost_lines` (`protected_lines.entries_missing`) and `put_back_lines` (review/review_loop_put_back.py), and files an ask per lost line. Only the changed sign-off lines go back.
  - `own_guard_test(signoffs)` makes the scope guard treat those files as in scope (`has_own_guard`). Wired at review_loop_script.py:610, :628-629 (`undo_protected_edits`).
  - Finding routing: `split_signoff_items` sends findings on sign-off lines to asks or hand-back edits instead of a coder.
- `lib/protected_lines.py` (212 lines): no loop knowledge. `entries_missing`, `restore_protected_lines(before_text, after_text, protected_numbers, whole_stretch, may_replace)`, `changed_line_ranges`, `changed_stretches`, `rewritten_stretches`, `consecutive_runs`, `line_opcodes`. Used by `review_loop_signoffs.py` (via `review_loop_put_back`) and `review_loop_comment_removal.py:196-200`. It has no reference to the scope guard.
- Fault lists aggregated in `review_loop_coder.coder_fault_notes()` (:22-27): `UNTRACKED_FAULTS`, `HELD_FAULTS`, `RULED_OUT_FAULTS`, `SCOPE_FAULTS`, `RULING_CHECK_FAULTS`.

### 7. Asks and fix text changes

- `review_loop_script.add_ask(agent, item)` (:555) appends to `self.asks`, `ask_rounds[item]` and `ask_gates[item]`. It dedups on the same item or on one `unseen` from earlier rounds.
- After each pass, `ask_for_approval_only_edits(changed, findings)` (review/review_loop_ruled.py:449) reverts the pass's edit to each approval-only file and returns the reverted paths:
  - A revert that fails files an approval ask (`file_approval_ask`).
  - `ask_for_wanted_changes` (:~490) files one ask per finding on a reverted path: "A fix coder wants to edit `<path>` for the finding ... Change: ... (edit to `<path>`)". `file_wanted_ask` (:~512) dedups, drops a rejected ask (`rejected_by_title`), and records a `wanted_entry`.
  - `save_approval_paths` (:~733) calls `write_saved_asks(repo, paths, wanted)`.
- `approval-asks.json` (`APPROVAL_ASKS_NAME`, lib/review_fix_names.py:13), in the review-fix folder beside the state file. Shape: `{"paths": {path: blob-id|None|"unknown"}, "wanted": [{text, change, path, line, title}]}`.
  - Reader/writer: `review/approval_asks_store.py` `read_saved_asks` (:100), `write_saved_asks` (:137) (atomic), `is_wanted_entry`, and `ApprovalAsksFileError` on a damaged file.
  - A resumed loop reads it in `resume_approval_asks(findings)` (review_loop_ruled.py:739). It re-files each path whose content still differs from the saved base blob and is not ruled or rejected. `resume_wanted_asks` re-files the saved wanted asks.
  - Held changes are in `held-approval-changes.json` (`HELD_APPROVAL_NAME`; `read_held_changes`, `write_held_changes`, `forget_held_changes`).
  - Rulings remove entries: `forget_ruled_approval_paths` (approval_asks_store.py:225).
- `lib/ruled_change_text.py` (62 lines, stdlib only):
  - Clauses `USER_CLAUSE`, `SESSION_CLAUSE`, `UNNAMED_CLAUSE`, and `PLACE_MARKER = "; make this change in its place: "`.
  - `changed_text(base, note, ruler_clause)`, `ruled_note(text)` (note after the last marker), `is_no_code_ruling(note)`, `is_no_code_finding(text)` (regexes `NO_CODE_RULING`, `CLAUSE_BREAK`, `EDIT_VERB_START`, `NEGATED_EDIT`, `TEST_WORD`).
  - Writers: `review/review_fix_asks.py:267, :275` (`ask_finding_text` builds an accepted ask's finding text with a note and `ruler_clause(decided_by)`).
  - Readers: `review_loop_ruled.py:54` (`is_no_code_finding`, `ruled_note`), used by `no_code_numbers` (:90), `ruling_line` (:123), `is_approval_ruling` (:791) and `flag_broken_no_code_rulings` (:795-815). The last records into `no_code_ruling_broken` the code files a pass changed against a no-code ruling.
- `review/phase_asks.py` (ruling command): `rule_open_asks(words)` (:342), `command_rule` (:331), `log_outcomes` (:305), `split_ruler` (:259), `verified_phase_relay` (:275), `main` (:437). `refuse_outside_repo` (:200).

### 8. Plan text in `lib/plan_format.py`

- 1764 lines. Regex/constants block (:39-105) and `PlanFormatError`, `NoCriteriaHeadingError` (:107-111).
- Phase structure:
  - `PHASE_HEADING = ^(#{2,4})\s+Phase\s+<PHASE_ID>` (:46)
  - `phase_spans(lines)` (:137)
  - `phase_section` (:179)
  - `parse_plan(lines, closing_skill)` (:340)
  - `parse_plan_with_closing_phases` (:730)
  - `phase_text` / `phase_line_range` (:735, :743)
- Phase Status lines: `PHASE_STATUS_LINE` (:58), `phase_status_entries(lines, closing_skill)` (:246) returning entries and failures; moved phases via `MOVED_MARK`, `MOVED_TARGET`, `moved_phases` (:376).
- Files per phase: `FILE_ENTRY`, `file_entry_paths(plan_lines, section)` (:199), `named_paths(text, repo_dir)` (:185), `PATH_IN_BACKTICKS` (:39).
- Verification: `manual_verification(text, name)` (:456), `automated_verification_rows` (:524), `verification_list_items` (:572), `AUTOMATED_HEADING` (:496), `deferred_verification_tag` (:611), `gate_env*` (:623-689).
- Plan folder: `PLANS_DIR = "docs/plans/"` (:506), `QUESTIONS_FILE_NAME`, `RESEARCH_FILE_NAME`, `SPEC_FILE_NAME`; `plan_folder(plan)` (:751), `outside_plan_folder(files, plan)` (:762), `plan_folder_exclude(plan)` (:772). The loop uses `outside_plan_folder` in `review_scope()` (review_loop_script.py:417-418) and `review_launch.py:650-653`.
- Plan impact and rulings: `PLAN_IMPACT_*`, `plan_impact_cause`, `resolved_plan_texts(handoff)` (:967), `ruling_owner`, `ruling_deviation`, `append_deviation` (:780), `SESSION_RULING` / `USER_RULING` (:875-876), `DECISION_LOG_NAME`, `CRITERIA_FILE_NAME`, `TICKET_FILE_NAME` (used review_loop_prompt_file.py:~250). Criteria: `CRITERION_LINE`, `AC_REFERENCE` (:1022-1023), `criteria_ids` (:806).
- Failures surface as `PlanFormatError`. `review_loop_main.py:~231` stops on it as `critical-blocker`: "the plan's standing ruling does not parse". `review_loop_script.py:~590` re-raises it from `repair` when the standing rulings are malformed.

### 9. Fix-pass result and state types, fields and JSON keys

- `CoderResult(report, diffs, changed, reverted=())` (review/review_loop_coder.py:~75): a NamedTuple. `changed` lists the paths whose text differs. `without_reverted(result, reverted, stats_before)` (:86) removes reverted paths and their diffs.
- `CoderCallError` with `changed`, `cause`, `diffs`, `died`, `keeping_only(kept)`. `failed_call_error(...)`. `changed_paths(before, after)` diffs two `file_texts` snapshots (:~66). `file_texts(repo, start=None)` uses `changed_files_since(repo, start)` (review_loop_plan.py:52).
- `FIX_DIFF_STATS` global list (review_loop_closure) records per-path diff stats of fix calls. `write_fix_diffs` writes one diff file per changed path under `out`.
- Loop state (review_loop_script.py ~395-410, `progress = {"iter", "fixed", "files_touched": set()}` at review_loop_main.py:279): `files_touched`, `held_files`, `ruled_out`, `later_phase_files`, `put_back_findings`, `open_fixes`, `no_code_broken`, `wanted_entries`, `approval_ask_paths`, `approval_ask_bases`, `kept_held_bases`, `kept_held_wanted`, `review_base`, `given_base`, `only_files`, `gate_commands`, `change` (ChangeUnderReview).
- Packet JSON keys: `status`, `iter`, `review_round`, `fix_rounds`, `post_cap_passes`, `fixed`, `skipped_fp`, `held_unfixed`, `blockers`, `findings_remaining`, `ask`, `plan_impacts`, `class_closure`, `open_classes`, `files_touched`, `nit`, `full_check*`, `base_used`, `given_base`, `scoped_tests`, `check_overridden`, `left_alone`, `check_changed`, `check_rewrote_edited`, `check_created`, `tool_fault`, `no_code_ruling_broken`, `adopted_unapplied`, `against_ruling`, `handback_edits` (review_loop_packet.py:66-110).
- `handback.py` `STR_KEYS` / `LIST_KEYS` (:73-82) parse those keys. `fixed_paths(packet)` (:587) derives from `fixed[]` and `files_touched`.
- `lib/review_fix_names.py` (42 lines, no imports):
  - Folder/file names: `REVIEW_FIX_FOLDER`, `STATE_FILE_NAME`, `ASK_FINDINGS_NAME`, `BLOCKER_TEXT_FOLDER`, `APPROVAL_ASKS_NAME`, `HELD_APPROVAL_NAME`, `PARTIAL_FIX_NAME`, `RUN_FOLDER_FINDINGS_NAME`.
  - State keys: `FILED_AT_KEY`, `PLAN_IMPACT_FILED_AT_KEY`, `PENDING_LAUNCH_KEY`, `CORRECT_OPEN_KEY`, `ASKS_DECIDED_BY_KEY`, `RESTORED_INDEXES_KEY`.
  - `PACKET_IDENTITY_KEYS = ("skill","scope","lane","iter","review_round","spec_iter","fix_rounds","post_cap_passes","status","branch","source","fixed_paths","files_touched")`.
- `review/review_fix_state.py` (199 lines): re-exports those names. It defines `SAME_RUN_STATE_KEYS` (:~46-73), `read_state`, `save_fix_state` (atomic JSON), `review_fix_dir()`, `review_fix_state_file()`, `clear_asks_launch_pending`, `has_unanswered_asks`, `UsageError`, `argument_parser`. State lives at `<git dir>/review-fix/state.json`. It has no fix-pass `changed` list of its own. The packet's `files_touched` and `fixed_paths` are listed in `PACKET_IDENTITY_KEYS`.
- Partial fix record (`PARTIAL_FIX_NAME`, review_loop_partial_fix.py): `saved_findings`, `saved_findings_not_in_header`, `coder_failure_blocker(call_name, error, scope_guard_failed, died)` (:170). `CoderFailedError` is raised before any pass when the scope guard cannot read the repo (review_loop_script.py:611-615).

### 10. Tests

- Path helper: tests/scripts/toolkit_paths.py. `CLAUDE_DIR` (env `TOOLKIT_CLAUDE_DIR` or the tree's), `SCRIPTS_DIR`, `REVIEW_DIR`, `LIB_DIR`, `CODE_DIR`, `TOOLS_DIR`, `GATES_DIR`, `TELEMETRY_DIR`, `REPO_ROOT`, `script_in(scripts_root, name)`, `first_python_that_starts`, `guard_real_ledger`, `absolutize_import_paths`, `REAL_PLANS_ENABLED`, `CODER_GATE_LIB_MODULES`. Tests insert `toolkit_paths.LIB_DIR` and `REVIEW_DIR` into `sys.path`.
- tests/scripts/test_review_loop_scope_guard.py (1322 lines), the put-back tests:
  - `ScopeGuardTest` (:32) unit-tests `guard_pass` and `undo`.
    - `setUp` makes a tmp git repo with `app.py`, `docs/rule-anchors.md`, `tests.py` and `docs/plans/shop/plan.md`, one commit, then edits `app.py`.
    - `guard()` wraps `guard_pass(repo, out, "coder1", allowed, has_own_guard, finding_texts, gate_passes)`.
    - Clears `SCOPE_FAULTS` in setUp.
    - Fix passes are simulated by writing files, `git add`/`commit` and mocks.
    - Covered cases: clean/dirty/staged/committed/deleted/renamed files put back, names in findings (dot-slash, suffix, ambiguous suffix), failures (`git restore`, index listing, status, HEAD lookup, copy), put-back folder bytes, gate verdict paths (needed, not needed, no gate, deleted, multiple strays).
  - `StubLoop` (:1073) and `StrayGateTest` (:1096) cover `stray_gate_passes`.
  - `ScopeGuardLoopTest(loop_tests.ReviewLoopHarness, unittest.TestCase)` (:1160) runs the whole script. `fix_with_notes_edit` runs `run_script` with a scenario dict (`code-reviewer`, `coder` with `edits`, `closure`) plus optional `gate_command`. Tests assert on `self.stored_packet()`, e.g. a stray file the gate does not need stops with `critical-blocker` (:1173), and an out-of-diff edit is put back and named in `tool_fault` (:1209).
- tests/scripts/test_review_loop_script.py: `ReviewLoopHarness` (:662) provides the scratch repo `shop-api` on branch `main`, a fake `claude` and `ruff` on PATH (`FAKE_CLAUDE`), a fake ledger, `commit_files`, `prompt_file_text`, `script_command`, `run_script`, `stored_packet`, `state_dir` and the constants `APP_BEFORE`, `APP_AFTER_EDIT`, `APP_FIXED`, `NOTES_BEFORE`, `NOTES_REFLOWED`, `FIX_REVIEW`, `CLEAN_REVIEW`, `CLOSED`, `AGENT_ID`, `SESSION`.
- Other tests: test_review_loop_ruled.py, test_review_loop_coder.py, test_review_loop_prompt_file.py, test_review_loop_round_two_fixes.py, test_review_loop_findings.py, test_review_loop_closure.py, test_review_loop_named_tests.py, test_review_loop_repeats.py, test_review_loop_prompts.py, test_review_loop_nearest.py, test_review_loop_round_audit.py, test_merge_free_base.py, test_review_launch.py, test_ruled_change_text.py, test_protected_lines.py, test_signoff_lines.py, test_untracked_listing.py, test_file_backup.py, test_plan_format.py. Fixture: tests/scripts/fixtures/packets/review-loop-critical-blocker.txt.
- Tests of a base inside the loop: none found for `review_base` in test_review_loop_script.py (the rg for `BASE_KEY|review_base|"base"` returned only line 4232, `tree = temp / "base"`, which is not a review base). The base header is covered at the launcher (test_review_launch.py:335-403).
- Runner: `python3 tests/parallel_tests.py <file>`, `bash tests/run.sh`, `bash tests/lint.sh <files>` (docs/toolkit-script-rules.md).

## Dormant scaffolding (on the questioned surfaces)

- `merge_free_base.BaseResolution.commit` is read only by `given_if_moved` (lib/merge_free_base.py:48-52).
- `merge_free_base.merge_free_base` has no caller in the review-loop mixins. Its callers are `code/code_review_start.py:423` and `code/phase_start.py:214`. `review_launch.resolved_base` calls `resolve_base` only.
- `review_blocker_text.blocker_text` has no caller in the loop's modules (`review_loop_*`, `handback.py`), only `review/review_fix.py:515,523`.
- `ScopeGuard.keep_bytes_of` / `put_back_everything` are called only inside the class.
- `script_utils.staged_paths` equivalent: `worktree_snapshot.staged_paths(root)` (:57) has no caller in scripts (`rg -F "staged_paths("` hit only its definition).
- `review_fix_state.PACKET_IDENTITY_KEYS` is imported from `review_fix_names` (5 hits in scripts, 0 test files).

## Code References

- TK/lib/merge_free_base.py:37,55,80,91,103,128 - `BaseResolution`, `resolve_base`, `merge_commits`, `merged_in_parents`, `fold_parent`, `merge_free_base`
- TK/review/review_launch.py:194-203 - `resolved_base`; :640-641, :678 - `used` and `given_if_moved` into the header
- TK/code/code_review_start.py:416-430, :452-456 - `diff_base` and `ReviewScope.review_base`/`given_base`
- TK/code/phase_start.py:211-217 - `own_tick_base`
- TK/review/review_loop_main.py:157-158 - reads `BASE_KEY` and `GIVEN_BASE_KEY` into the loop; :221-223 - `StrayFileError` stop
- TK/review/review_loop_script.py:401-402, :414-419 - `review_base`, `given_base`, `review_scope()`
- TK/review/review_loop_script.py:586-651 - `repair` (guard_pass at :609, coder_call at :635, stop_on_stray_files at :648)
- TK/review/review_loop_script.py:652-659 - `pass_scope`
- TK/review/review_loop_plan.py:23-49, :90-99, :142 - `scope`, `base_scope`, `ChangeUnderReview`, `review_files`
- TK/review/review_loop_pass_checks.py:34-42 - `keep_coder_commit_in_scope`
- TK/review/review_loop_scope_guard.py:19-27, :34-39, :42-54, :318-339 - `SCOPE_FAULTS`, `PassScope.holds`, `paths_differing_from_head`, `guard_pass`
- TK/review/review_loop_scope_guard.py:152-174, :221-253, :290-316 - `changed_clean_files`/`put_back_clean_files`, `keep_needed_files`, `note_faults`
- TK/review/review_loop_stray_files.py:20-44 - `stray_gate_passes`, `stop_on_stray_files`
- TK/review/review_loop_coder.py:22-27, :115-194 - `coder_fault_notes`, `coder_call`, `undo_pass`
- TK/review/review_loop_ruled_out.py:112 - `begin_pass`; review_loop_untracked.py:69 - `begin`
- TK/review/review_loop_signoffs.py:~195 - `undo_signoff_pass`
- TK/review/review_loop_ruled.py:449, :739, :795 - approval/wanted asks, resume, no-code rulings
- TK/review/approval_asks_store.py:100, :137 - `read_saved_asks`, `write_saved_asks`
- TK/lib/review_fix_names.py:13 - `APPROVAL_ASKS_NAME`
- TK/lib/ruled_change_text.py:19,24,36,45,56 - `changed_text`, `ruled_note`, `asks_for_test_edit`, `is_no_code_ruling`, `is_no_code_finding`
- TK/lib/script_utils.py:440, :602, :1000, :1035 - `index_entries`, `repo_file_paths_or_raise`, `texts_relative_to`, `texts_name_repo_file`
- TK/lib/worktree_snapshot.py:24-62 - `status_entries`, `status_codes`, `file_hash`
- tests/scripts/test_review_loop_scope_guard.py:32, :1073, :1096, :1160 - the four test classes
- tests/scripts/test_review_loop_script.py:662 - `ReviewLoopHarness`
- tests/scripts/test_merge_free_base.py:27, :156 - base tests

## Patterns Found

- Base resolution happens in the launchers (`review_launch.py`, `code_review_start.py`). The loop reads the resolved commit from the prompt header (`base:`, `given-base:`) as `review_base`.
- `review_launch.py` composes only `resolve_base`. `code_review_start.py` composes `resolve_base` then `merge_free_base`.
- Guards follow one shape: a `begin`/`guard_pass` snapshot before the call, an `undo()` after it, a module-level list of fault notes (`SCOPE_FAULTS`, `RULED_OUT_FAULTS`, `UNTRACKED_FAULTS`, `HELD_FAULTS`, `RULING_CHECK_FAULTS`) read by `coder_fault_notes()`, and backups under `<out>/pass-backup/<role>/...`.
- The scope guard identifies changed files by comparing the live tree and index to the pass-start state (`status_codes`, `index_entries`, `git diff <head>`), not from the coder's report. `CoderResult.changed` comes from a separate `file_texts` before/after text diff.
- File sets are `str` repo-relative paths. Fuzzy matching is only against finding text.
- Stop reasons are plain text in the packet. The loop wraps typed errors (`StrayFileError`, `CoderFailedError`, `RulingBrokenError`, ...) into `loop.stop("critical-blocker", [str(error)])`.
- Persisted ask state is JSON written with `write_text_atomically` in `<git dir>/review-fix/`.
- Tests build a throwaway git repo and drive `guard_pass`/`undo` directly. Loop-level tests drive the full script through `ReviewLoopHarness.run_script` with a fake `claude` and scripted `edits`.

## Reuse Inventory

- `merge_free_base.resolve_base(repo, base, name=None) → BaseResolution` — TK/lib/merge_free_base.py:55 — a base replaced by its merge base with HEAD when it is no ancestor.
- `merge_free_base.merge_free_base(repo, base) → commit` — TK/lib/merge_free_base.py:128 — a base with merged-in parents folded in.
- `BaseResolution.given_if_moved() → str|None` — TK/lib/merge_free_base.py:48 — the given name only when `used` moved.
- `merge_commits(repo, base)`, `merged_in_parents(repo, merge)`, `conflicted_paths(output)`, `fold_parent(repo, merge, current, parent)` — TK/lib/merge_free_base.py:80,91,~102,~118 — helpers.
- `review_launch.resolved_base(repo, base) → BaseResolution` — TK/review/review_launch.py:194 — wraps the ref lookup and `resolve_base` into `LaunchError`.
- `code_review_start.diff_base(repo, base_commit, base) → commit` — TK/code/code_review_start.py:416 — resolve then merge-free, exits on error.
- `review_loop_plan.review_files(repo, base="", only=()) → {path: [added, status]}` — TK/review/review_loop_plan.py:142 — files under review.
- `review_loop_plan.base_scope(repo, base)` / `scope(repo)` / `changed_files_since(repo, start)` — TK/review/review_loop_plan.py:32,23,52.
- `review_loop_scope_guard.guard_pass(...) → ScopeGuard` — TK/review/review_loop_scope_guard.py:318.
- `PassScope.holds(path)` — scope_guard:34.
- `paths_differing_from_head(repo, head, *diff_options) → set` — scope_guard:42.
- `ScopeGuard.undo(judge=True)`, `stray_files()`, `stray_blocker_text(strays, reason)`, `keep_needed_files()`, `needed_strays(strays)`, `restore_pass_state(strays)`, `keep_bytes_of(paths)` — scope_guard methods.
- `review_loop_stray_files.StrayFiles.stray_gate_passes()`, `.stop_on_stray_files(scope_guard, findings, result)`; `StrayFileError` — TK/review/review_loop_stray_files.py:20-44.
- `review_loop_coder.coder_call`, `coder_fault_notes()`, `changed_paths(before, after)`, `file_texts(repo, start=None)`, `without_reverted(...)` — TK/review/review_loop_coder.py.
- `review_loop_ruled_out.begin_pass(repo, out, role, ruled_out, diff_files, finding_texts) → PassGuard`; `names_deletion(finding_texts, path, root)`; `skip_ruled_out(items, ruled_out, skipped_fp, repo)` — TK/review/review_loop_ruled_out.py.
- `review_loop_untracked.begin(repo, out, deletable=())`, `guarded_untracked`, `record_loop_written`, `note_removal` — TK/review/review_loop_untracked.py.
- `review_loop_signoffs.snapshot_signoffs`, `lost_lines`, `handback_edit`, `signoff_ask`, `SignoffRuns.undo_signoff_pass` — TK/review/review_loop_signoffs.py.
- `protected_lines.entries_missing`, `restore_protected_lines`, `changed_line_ranges`, `changed_stretches`, `rewritten_stretches`, `consecutive_runs`, `lines_rewritten_in_place` — TK/lib/protected_lines.py.
- `file_backup.save_files(root, paths, backup_dir, max_file_bytes)`, `restore_missing`, `saved_paths_that_differ`, `restore_changed`, `restore_paths`, `put_back_all`, `discard`, `Backup` — TK/lib/file_backup.py:13-115.
- `script_utils.git_output(cwd, *args, timeout=None)` (:360), `index_entries(repo, paths)` (:440), `index_entry(repo, path)`, `restore_index_entry(repo, path, entry)` (:469), `restore_index_entries(repo, entries_before)`, `head_commit_or_unborn(repo)` (:543), `untracked_paths(dir)` (:585), `repo_file_paths(dir)` / `repo_file_paths_or_raise(dir)` (:602), `texts_name_repo_file(texts, path, root, known_paths)` (:1035), `texts_relative_to`, `names_path`, `path_has_tail`, `without_paths(files, paths)` (:1231), `next_numbered_dir(parent)` (:1778), `one_line(text, limit)` (:969), `GitCallError` (:286), `IndexEntry` (:437), `PATH_TOKEN_START/END` (:985-986) — TK/lib/script_utils.py.
- `worktree_snapshot.status_entries/status_codes(root, strict)`, `file_hash(root, path)`, `working_tree_changes(root)`, `work_tree_tree(repo)`, `take`, `changes_since` — TK/lib/worktree_snapshot.py:24-146.
- `review_blocker_text.blocker_text(text)`, `full_text_file(text)` — TK/review/review_blocker_text.py.
- `approval_asks_store.read_saved_asks`, `write_saved_asks`, `read_approval_paths`, `read_held_changes`, `write_held_changes`, `forget_held_changes`, `forget_ruled_approval_paths`, `approval_change`, `wanted_entry`, `is_approval_ask` — TK/review/approval_asks_store.py.
- `ruled_change_text.changed_text`, `ruled_note`, `is_no_code_ruling`, `is_no_code_finding`, `asks_for_test_edit` — TK/lib/ruled_change_text.py.
- `plan_format.outside_plan_folder(files, plan)` (:762), `plan_folder(plan)` (:751), `plan_folder_exclude(plan)` (:772), `phase_spans`, `parse_plan`, `phase_status_entries`, `file_entry_paths`, `named_paths` — TK/lib/plan_format.py.
- `review_fix_names.*` constants and `PACKET_IDENTITY_KEYS` — TK/lib/review_fix_names.py; `review_fix_state.read_state/save_fix_state/review_fix_dir` — TK/review/review_fix_state.py.
- Test helpers: `ScopeGuardTest.guard(...)` / `git(cwd, *args)` (tests/scripts/test_review_loop_scope_guard.py:28-66); `ReviewLoopHarness` (tests/scripts/test_review_loop_script.py:662); `StubLoop` (test_review_loop_scope_guard.py:1073); `toolkit_paths.*`.
