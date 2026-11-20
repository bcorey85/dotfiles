# Hooks and hand-off batch: fork dispatch, safe pulls, refactor-flow files, miss_reason kept, approval edits reverted, held user-only asks

Fix six queued toolkit defects. Each phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/` and `claude/.claude/skills/refactor/scripts/`; tests in `tests/scripts/`, paths from
`tests/scripts/toolkit_paths.py`.

## Scope

- In: `agent-model-guard.sh`, `tools/pull_keep_index.py`, `skills/refactor/scripts/refactor_flow.py`,
  `skills/close-branch/SKILL.md` Step 5, `telemetry/log-escape`, `telemetry/log-escape-check`,
  `telemetry/ledger-write` (header doc only), `review/review_loop_ruled.py` (only the approval-only ask path:
  `ask_for_approval_only_edits`, `resume_approval_asks`, and new functions beside them), `review/review_fix_asks.py`,
  `review/review_asks.py`, `lib/ask_outcome_words.py`, and the tests of each.
- Out: `review-commit-gate`, `staged_claim_gate`, the test-command gates, the review loop's finding logic, the
  adopted-plan-impact path of `review_loop_ruled.py` (other lanes own them); `settings.json`; any CLAUDE.md.

## Phase Status

- [x] Phase 1: agent-model-guard lets a fork dispatch through (risk: low)
- [x] Phase 2: pull_keep_index pulls nothing when the upstream is already in HEAD (risk: medium)
- [x] Phase 3: refactor_flow takes untracked files and keeps its log input in the git dir (risk: low)
- [x] Phase 4: log-escape keeps miss_reason in the local escape text for every stage (risk: low)
- [x] Phase 5: the review loop reverts a fix coder's approval-only edit and reports it (risk: medium)
- [x] Phase 6: asks-done records session rulings while a user-only ask stays held (risk: medium)

## Phase 1: agent-model-guard lets a fork dispatch through

Bug: an `Agent` call with `subagent_type: "fork"` and no `model` is denied with "no model pin" (no agent file
exists for `fork`). A fork always runs on the parent model, and the harness ignores a `model` on it.

1. `agent-model-guard.sh`: right after the subagent type is read, `subagent_type == "fork"` exits 0. Add the case to
   the header's numbered logic.

#### Automated Verification

- New `tests/scripts/test_agent_model_guard.py` (script path from `toolkit_paths.py`, env override): a fork with no
  model passes (exit 0, no deny); a non-fork agent with no pin and no agent file is denied; `model: "opus"` on a
  non-fork agent is denied.
- `python3 tests/parallel_tests.py test_agent_model_guard.py` passes.

## Phase 2: pull_keep_index pulls nothing when the upstream is already in HEAD

Bug: a feature branch was pushed, then the integration branch was merged into it locally, so `@{u}` is an ancestor
of HEAD. `git pull --rebase=merges` still rebased and rewrote every commit hash, the pushed integration commits
included; the push then needs a force.

1. After the fetch, one upstream-relation check (refactor `rewritten_locally` into it): when the upstream tip is an
   ancestor of HEAD, pull nothing, print one line saying the branch already holds the upstream, and exit 0 with the
   index untouched. A branch rewritten locally keeps today's "Push with --force-with-lease" path. A branch another
   machine pushed to still pulls.

#### Automated Verification

- `tests/scripts/test_pull_keep_index.py`: a fixture with a pushed feature branch and a local merge of master leaves
  HEAD's hash unchanged and exits 0; a branch behind its upstream still pulls; a staged file stays staged in both.
- `python3 tests/parallel_tests.py test_pull_keep_index.py` passes.

## Phase 3: refactor_flow takes untracked files and keeps its log input in the git dir

Bugs: `simplify-prep` on a target holding only untracked files prints STOP (it lists files with `git ls-files`).
`fresh_log_input()` writes the branch log input under the system temp folder, which is gone by the time close-branch
logs; and close-branch Step 5 never names the `log --mode branch` command.

1. `tracked_files` (rename to fit) lists `ls-files --cached --others --exclude-standard` for the target.
2. `fresh_log_input()`: with no `REFACTOR_LOG_INPUT_DIR`, the default folder is `git rev-parse --git-path
   refactor-flow` of the repo, created when missing.
3. `skills/close-branch/SKILL.md` Step 5: add the step that runs `python3
   ~/.claude/skills/refactor/scripts/refactor_flow.py log --mode branch --base <base> --input <the path branch-prep
   printed>`.

#### Automated Verification

- `tests/scripts/test_refactor_flow.py`: simplify-prep on a target with one tracked and one untracked file lists both;
  on a target with only untracked files it does not STOP; the log input path with no env override sits under the
  repo's git dir.
- `python3 tests/parallel_tests.py test_refactor_flow.py` passes.

## Phase 4: log-escape keeps miss_reason in the local escape text for every stage

Bug: the installed ledger refuses `miss_reason`; log-escape resends the row without it, so the label every caller
supplies is lost. escape-text.jsonl keeps rows only for hand-catch stages with a desc.

1. `log-escape`: every row with a `miss_reason` writes a local escape-text row holding it (through `ledger-write
   --local escape_text`), whatever the stage and with or without a desc. The hand-catch text row stays as it is.
2. When the ledger refuses the field, the note reads that the ledger build does not store miss_reason, the row is
   logged without it, and miss_reason was kept in the local escape text file (name the file).
3. `ledger-write` header: escape_text holds a review_escape row's catch text and its miss_reason.
4. `log-escape-check`: match the new note; check the local file holds the miss_reason.

#### Automated Verification

- A test in `tests/scripts/` runs log-escape with a stub ledger that refuses `miss_reason`, for a non-hand-catch stage
  with no desc: exit 0, the note names the local file, and that file's row holds the miss_reason. With a ledger that
  stores it, the local row is still written.
- `bash claude/.claude/scripts/telemetry/log-escape-check` shows no new FAIL against the master run (its reject-line
  FAILs are ledger-side).
- `python3 tests/parallel_tests.py <the test file>` passes.

## Phase 5: the review loop reverts a fix coder's approval-only edit and reports it

Bug: a fix coder's edit to CLAUDE.md, CLAUDE.local.md or AGENTS.md is filed as a user-only ask; asks-done then needs
the user, who does not answer panes. A re-run files the same ask after the session reverted the edit, though the file
has no diff against HEAD.

Ruling (agent-evals-5e, 2026-11-19): revert and report every fix-coder edit to those files; file no ask for a file
with no diff against HEAD.

1. New function in `review_loop_ruled.py` (called from `ask_for_approval_only_edits`, which keeps its signature and
   call sites): for each approval-only file the pass changed that no ruling settles, restore the file to its
   pre-pass blob from `approval_blobs` (delete a file the pass created), and record it in `dropped_asks` with a named
   reason constant saying the fix coder's edit was reverted. No user-only ask is filed for it.
2. `resume_approval_asks`: a saved path whose file has no diff against HEAD (tracked and unchanged, or absent) is not
   filed again and leaves the saved paths.
3. Callers of `user_only_asks` and `save_approval_paths` still read correctly when nothing is filed.

#### Automated Verification

- Tests in the review loop test file: a coder pass that edits CLAUDE.md leaves the file at its pre-pass content, files
  no user-only ask, and the packet's dropped asks name the file; a coder pass that creates AGENTS.md removes it; a
  saved approval path whose file was reverted to HEAD before the re-run files no ask.
- `python3 tests/parallel_tests.py <the changed test files>` passes.

## Phase 6: asks-done records session rulings while a user-only ask stays held

Bug: asks-done needs one outcome per ask in one call, and a session call is refused when any ask is user-only, so the
plain asks a session can rule stay unlogged until the user answers.

1. `lib/ask_outcome_words.py`: a new outcome word `held`, valid only on a user-only ask in a session call.
2. A session call on a packet with user-only asks gives `held` for each user-only ask and an outcome for each plain
   ask. Any other word on a user-only ask is still refused. The refusal text names `held`.
3. The plain asks are logged and their fix run printed as today. The held asks move into a new kept packet in
   `waiting_packets` (their own packet id, the parent's relaunch args), so the original packet is answered and a
   later `asks-done --by user --packet <new id>` rules them.
4. `held` on a plain ask, or `held` in a `--by user` call, is refused.

#### Automated Verification

- Tests in the review-fix test file: a packet with two plain asks and one user-only ask takes a session call with
  `held` on the user-only ask: the plain asks log, the fix run prints, the held ask waits in a kept packet; a later
  `--by user --packet <id>` call logs it; `held` on a plain ask is refused; `held` with `--by user` is refused.
- `python3 tests/parallel_tests.py <the changed test files>` passes.

## Plan Deviations

Phase 1 ruling (session, 2026-11-19, owner plan): agent-model-guard.sh and its test stay in this repo as the plan's Scope says; AC1 unchanged. The CB Security Hooks package must carry the fork pass too, or a regenerate drops it (follow-up for the work package).

Phase 4 ruling (session, 2026-11-19, owner plan): `ledger-write --local-path` is in scope for Phase 4; it keeps ledger-write the one owner of the type-to-file table; no AC changed.

Phase 5 ruling (session, 2026-11-19, owner plan): a resumed run that finds a saved approval path committed and matching HEAD files no ask and reports nothing; no code change. agent-evals-5e ruled "file no ask for a file with no diff vs HEAD"; no session hit the committed case, and the in-pass revert already catches a coder commit (it compares the pre-pass blob). AC7 unchanged.

Branch review asks (session, 2026-11-19, owner plan): a round finding whose fix path is a reverted approval-only file stays an open fix with the revert reason, not fixed or skipped_fp. A staged or committed approval edit has its index entry restored too; a committed one is also named in the packet's files touched so the session commits the revert; no user-only ask is filed. AC6 and AC7 unchanged.

Refactor review ask (session, 2026-11-19, owner plan): `without_reverted` keeps its header match through the shared `diff_old_label`; keying diffs by path is rejected, since existing tests build CoderResult diffs as plain strings. No AC changed.

Scope widening (session, 2026-11-19, owner plan): the phases also edit review_loop_script.py, review_loop_coder.py, review_loop_findings.py, review_fix.py, lib/script_utils.py, approval_asks_store.py, simplify_slices.py, _shared/review-fork-run.md, escape/SKILL.md, refactor/SKILL.md and docs/rule-anchors.md, as callers and docs of the in-scope changes; no AC changed. Also review_loop_ruled.py, lib/review_fix_names.py, close-branch/SKILL.md, telemetry/log-escape-check and their tests, for the same reason. review/full_check_gate.py takes the four-value `repair` return (branch review ask A). The branch-final refactor and its review also touch review/review_loop_closure.py (class receipt when a member's fix was reverted).
