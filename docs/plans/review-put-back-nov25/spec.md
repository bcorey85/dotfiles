# Five review-loop put-back and intake defects of 2026-11-25

> Ticket: ./00-ticket.md
> Decisions: ./03-decisions.md
> Date: 2026-11-25

## Summary

Five fixes to the review loop, one per phase. Finding paths may hold `$` and `+`. A removed comment that a finding quotes counts as named even when its line moved. A plan impact that points at a user ruling in the decision log is held as an ask, never adopted as code-wins. Every reviewer finding of a round reaches a coder brief or an ask before the next round, and a used review round cannot be dispatched again. The scope put-back never undoes an earlier round's fix, keeps a file the fix needs, stops instead of reverting silently, and names every reverted file and where its bytes went.

## Phase Status

- [x] Phase 1: Paths that hold `$` (risk: low)
- [x] Phase 2: Match a removed comment by content (risk: medium)
- [ ] Phase 3: Hold a plan impact that cites a user ruling (risk: medium)
- [ ] Phase 4: Every round finding reaches a coder or an ask; a used round is refused (risk: high)
- [ ] Phase 5: Scope put-back keeps earlier fixes and needed files (risk: high)

## Constraints

- Toolkit scripts follow `docs/toolkit-script-rules.md` and `claude/.claude/scripts/CLAUDE.md` (one owner per fact; tests in `tests/scripts/test_<script>.py` with paths from `toolkit_paths.py`).
- `review/review_loop_script.py` is at 989 lines: add no verb, route or state field to it (D4). New logic goes in a mixin or module of its own.
- Each phase adds a test that fails on the tree at 832ce08b4 and passes after, and one change file: `python3 ~/agent-evals/bin/build_changes.py new "<title>" --by claude-code/claude-opus-5-5 --root docs/changes`.
- Run changed test files through `python3 tests/parallel_tests.py <file>`; lint with `bash tests/lint.sh <changed .py>`.

## Implementation Plan

Paths are relative to the worktree root. `S` = `claude/.claude/scripts`, `T` = `tests/scripts`.

### Phase 1: Paths that hold `$`

#### Overview

`S/lib/script_utils.py:23` `PATH_CHARS = r"\w@.\-"` lacks `$`, so a finding on `src/routes/$id.test.tsx:12` parses to the wrong path and `review_loop_findings.names_absent_file` drops it as not in the tree. Estimate: 5 source + 40 test lines.

#### Changes Required:

1. `S/lib/script_utils.py`: add `$` and `+` to `PATH_CHARS` (D1). Check each regex built on it (`PATH_TEXT`, `PATH_LINE`, `LOCATION_ALONE`, `UNHOMED_PATH_LINE`, `BARE_PATH`, `DOT_SLASH_PATH`) and every other path regex in `S/` that `rg` finds for `\w@.` or `PATH_CHARS` copies, so all read the same path text.
2. Tests: `T/test_script_utils.py` (or the existing finding-parse test file): a finding on `src/routes/$postId.test.tsx:12` and one on `src/routes/+page.svelte:3` parse to that path and line; a review-loop intake test with a real `$` file in a temp repo keeps the finding (not in `skipped_fp` with "the file is not in the tree").

#### Success Criteria

A finding on a `$` path reaches the coder; every existing path-parse test passes unchanged.

#### Automated Verification:

- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_script_utils.py test_review_loop_findings.py`
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/lib/script_utils.py`

---

### Phase 2: Match a removed comment by content

#### Overview

`S/review/review_loop_comment_removal.py` `unnamed_removals(path, removed, spans, named)` matches a removed comment to a finding by line or span only (`named_locations`). When earlier edits moved the comment's line, a finding that names it misses, and the put-back restores it and files an ask. Estimate: 40 source + 60 test lines.

#### Changes Required:

1. `review_loop_comment_removal.py`: a removed comment also counts as named when a finding of the pass names its file and its text quotes the comment's text (whitespace-normalized, the comment marker stripped) (D2). Reuse an existing text normalizer from `lib/` if one fits (`rg` first). A finding that names the file but quotes nothing of the comment does not match.
2. Tests: `T/test_review_loop_comment_removal.py` (or the existing test file for it): a finding names `a.py:10` and quotes a comment that sits at line 14 before the pass; the pass removes it; it stays removed and no ask is filed (fails before). A removal no finding names by line, span or content is still put back and asked (AC12).

#### Success Criteria

A quoted comment whose line moved stays removed; an unnamed removal is still put back.

#### Automated Verification:

- [ ] **Test-verified**: the comment-removal test file passes through `python3 tests/parallel_tests.py`
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/review/review_loop_comment_removal.py`

---

### Phase 3: Hold a plan impact that cites a user ruling

#### Overview

`S/review/review_loop_ruled.py:346` `route_plan_items` adopts every plan impact with `acceptance_criteria: none` by rule, and `review_fix_plan_impacts.present_plan_impacts` prints it under "Plan impacts adopted by rule (... the code wins ...)" with a Plan Deviations line. When the impact's plan side is a user ruling recorded in the decision log, that line records the reverse of the ruling. Estimate: 40 source + 70 test lines.

#### Changes Required:

1. Add a reader (in `S/lib/signoff_lines.py`, the decision-log sign-off owner, or a small module beside it) that says whether an impact's text cites a sign-off line ruled by the user in the loop's plan folder decision log (`03-decisions.md`, or the plan's `## Plan Deviations`): the impact names the log and quotes that line's text or points at its line number (D3). Use `plan_format.USER_RULING` and the existing ruler parsing; add no second ruler regex.
2. `route_plan_items`: such an impact is recorded `adopted: False` and goes to `ruling_held`, so it is asked, never printed as code-wins.
3. Tests: `T/test_review_loop_ruled.py` or `T/test_review_fix_plan_impacts.py`: a plan folder whose `03-decisions.md` holds a dated user ruling, and a PLAN-IMPACT with `acceptance_criteria: none` whose `assumed:` quotes that line; the packet shows no Plan Deviations line for it and holds it for a ruling (fails before). An impact that cites no user ruling is still adopted by rule (AC14).

#### Success Criteria

A user-ruling impact is held as an ask; other no-criterion impacts are adopted as before.

#### Automated Verification:

- [ ] **Test-verified**: the changed test files pass through `python3 tests/parallel_tests.py`
- [ ] **Lint-verified**: `bash tests/lint.sh <changed .py>`

---

### Phase 4: Every round finding reaches a coder or an ask; a used round is refused

#### Overview

A round returned NEEDS CHANGES with a blocker and two fixes, but the next passes were only lint, full-check and class-closure coders, whose briefs held none of the reviewer's findings, and the re-review prompt (`prior_issues`) listed the round as all fixed. Separately, an orchestrator re-dispatched a stale review round after `code_wait` on an old output, and nothing refused it. Estimate: 80 source + 120 test lines.

#### Changes Required:

1. Trace, with a test that drives `walk()` through a round whose reviewer reports a blocker and fixes, every path by which a fix finding of `review_round()` misses `fix_round`'s `repair()` brief: dedupe through `earlier_filing`/`refile`, `split_review` drops, held or ruled-out files, `open_fixes` not carried into the lint, full-check and class-closure repair briefs, and `prior_issue_entries` marking findings fixed that no coder got. Fix each path found.
2. Add one check, run before the next review round is built, that every fix finding of the last round's reports is in a coder brief of this round or filed as an ask; a finding in neither goes to a coder pass (or, when that cannot run, the loop stops naming it). Put it in a mixin module, not in `review_loop_script.py` (D4).
3. Refuse a review-round dispatch whose round the loop has already taken in: find where the loop writes reviewer dispatch lines and reads reports back by round and role (the round/role lines added in review-loop-nov23 phase 5), and exit non-zero with a message that names the round, says it is used, and names the round to dispatch.
4. Tests: in `T/test_review_loop_script.py` or a new test file for the new module: the walk above fails before and passes after (every finding in a brief or an ask; the re-review prompt never lists an unsent finding as fixed); a re-dispatch of a used round is refused with that message.

#### Success Criteria

No reviewer finding is lost between rounds; a stale round dispatch is refused.

#### Automated Verification:

- [ ] **Test-verified**: the changed test files pass through `python3 tests/parallel_tests.py`
- [ ] **Lint-verified**: `bash tests/lint.sh <changed .py>`

---

### Phase 5: Scope put-back keeps earlier fixes and needed files

#### Overview

`S/review/review_loop_scope_guard.py` reverts every file a pass changed that its scope does not hold, and notes it only as "outside the review scope". A fix coder's edit to a file the fix needs (it defined a function the finding's file called) was reverted, and fixes from earlier rounds were undone, breaking the typecheck. Estimate: 100 source + 150 test lines.

#### Changes Required:

1. Earlier fixes (AC1): write a test where round 1's fix pass changes a file, and a later pass (round fix, lint, full-check or class-closure repair) runs with no finding naming that file. Walk every put-back the later pass runs (scope guard, ruled-out guard, sign-off and comment put-back, approval-only revert, ruling-check revert, failed-undo) and find which reverts round 1's hunk. A file every pass of the loop changed (not only round fix passes: check that `files_touched` gains the lint, full-check and class-closure passes' files too) is in every later pass's scope. Fix each path found.
2. Needed files (AC2): when a fix pass changed a file outside its scope, run the loop's gate for the pass (the scoped check it already runs after a pass; find it, do not add a second runner) with the file put back. If the gate fails with it put back and passes with the pass's bytes restored from the put-back folder, keep the file and note it as kept because the fix needs it. Otherwise stop the loop with a blocker that names the file and why (the gate passes without it, or fails either way, or no gate runs).
3. Report (AC3): every reverted file is listed in the packet with the folder its bytes were saved to (the guard's `put_back_dir`), and the stop text names them too.
4. Tests: `T/test_review_loop_scope_guard.py` and the loop test file: each of the three, failing before and passing after.

#### Success Criteria

An earlier round's fix survives a later pass; a needed file is kept; any other stray edit stops the loop naming the file; every revert names where its bytes went.

#### Automated Verification:

- [ ] **Test-verified**: the changed test files pass through `python3 tests/parallel_tests.py`
- [ ] **Lint-verified**: `bash tests/lint.sh <changed .py>`

## What We're NOT Doing

- No change to the gates or skills outside `claude/.claude/scripts/review/` and `claude/.claude/scripts/lib/`, except where a skill line names a changed message.
- No `[` `]` in path characters (D1).

## Plan Deviations

Phase 2: review ask on repeated identical comments ignoring line numbers was rejected by the session on 2026-11-25 (design choice beyond the phase); left for the user.
