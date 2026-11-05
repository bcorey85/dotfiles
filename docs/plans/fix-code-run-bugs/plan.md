# Lane 4: refactor log rows, decide without a packet, recap reads

Fix the queue items below. Each phase starts with a test that fails on the current tree.

## Scope

- In: `refactor_flow.py log` (miss reason, session-ruled plan-structure), `review_fix.py decide` with no packet state,
  `tools/ledger_deferred.py` refresh, `stage.mjs` output order.
  `tests/scripts/test_review_fix_script.py` (the cross-repo `asks-done` test compares the resolved temp path).
- Out: an amend verb for written rows (the ledger is append-only and has no row update); the peer-message double-coder
  report; any `~/agent-evals/bin/` file; `settings.json`.

## Phase Status

- [x] Phase 1: refactor_flow log takes the miss reason and a session ruling
- [x] Phase 2: review_fix decide works from the hand-back when no packet ran
- [x] Phase 3: branch-recap reads the jump queue and refreshes the ledger itself (risk: low)
- [x] Phase 4: refactor_flow log accepts a simplify target the branch deleted (risk: low)

## Phase 1: refactor_flow log takes the miss reason and a session ruling

File: `claude/.claude/skills/refactor/scripts/refactor_flow.py`, tests in `tests/scripts/test_refactor_flow.py`, prompt
in `claude/.claude/skills/refactor/SKILL.md` (the `log` input list).

1. An escape finding carries `miss_reason`, one label from `~/.claude/skills/_shared/escape-ratchet.md`. `log` refuses
   an escape finding with no `miss_reason` or a value outside the `log-escape` list
   (`out-of-scope|needs-other-file|needs-runtime|plan-gap|seen-dismissed|rule-absent|overlooked`; `unknown` is refused
   here because a model writes this input). The escape row sends the finding's value in place of `miss_reason=unknown`.
2. An ask finding (`disposition=ask`) may carry `ruled_by` (`user` or `session`, the same words
   `plan_format.is_ruling_by` accepts); `log` refuses `ruled_by` on any other disposition. A
   `plan_structure: true` finding with `ruled_by` may be logged `actioned=fixed` (disposition stays `ask`); without
   `ruled_by` the current refusal stands. A finding row with `ruled_by` sends `ask_decided_by=<value>` to
   `log-review-finding` (it already accepts that key).
3. SKILL.md: add `miss_reason` to the escape fields and `ruled_by` to the `[plan-structure]` rule, one line each.

#### Automated Verification

- New tests: escape finding without `miss_reason` refused; with one, the escape row carries it; plan-structure fixed
  with `ruled_by: session` is written with `ask_decided_by=session`; without `ruled_by` still refused; `ruled_by` on a
  non-ask row refused.
- `python3 tests/parallel_tests.py test_refactor_flow.py` passes.

## Phase 2: review_fix decide works from the hand-back when no packet ran

File: `claude/.claude/scripts/review/review_fix.py`, tests in `tests/scripts/test_review_fix_script.py`.

In a `/code` run the fork reads the packet through `code_wait.py`, so `review_fix.py packet` never runs and no fix
state exists. The commit gate then names `decide`, and `decide` fails with "no packet was processed".

1. When `decide` finds no fix state file, read the held plan impacts from the hand-back store:
   `handback.unruled_plan_impacts(handback_store.latest_for_repo(<CLAUDE_CODE_SESSION_ID>, <repo top>))`, the same
   read `review_commit_gate.py` makes. None held (or no session id) → the current "no packet was processed" error.
2. `decide keep` with held impacts: write the deviation entry (to `--plan`, else print the lines) and record the
   ruling with `record_ruling(session, "keep", ...)`. Print `ACTION: done`.
3. `decide adopt` with no fix state: write the deviation entry the same way, record nothing, and print a stop that
   says the review must run again through the caller's own loop (`/code resume`), since no `launch` state exists to
   re-dispatch from.
4. `decide discuss` keeps its output.
5. In `test_asks_done_from_another_repo_names_the_directory_it_looked_in`, compare against `other_repo.resolve()`, not
   the raw temp path.

#### Automated Verification

- New tests (with a planted hand-back row holding one held plan impact and no fix state): `decide keep --by session
  --ruling x` exits 0 and records the ruling; `decide adopt` prints the stop; with no hand-back the old error stays.
- `python3 tests/parallel_tests.py test_review_fix_script.py` passes.

## Phase 3: branch-recap reads the jump queue and refreshes the ledger itself

1. `claude/.claude/skills/stage/scripts/stage.mjs`: print the `jump-queue` block before the tier report, so a cut
   tool output keeps it. Test in `tests/scripts/test_stage_run.py`: the block comes before the first tier heading.
2. `claude/.claude/scripts/tools/ledger_deferred.py`: on `LedgerBusyError`, run `ledger worker --once` itself (with a
   timeout), then read once more. Still busy, or the worker fails → the current `not read` line and exit 75, naming
   that the worker ran. Tests in `tests/scripts/test_ledger_deferred.py` with the planted `ledger` stub: busy, then
   worker, then the queue prints.
3. `claude/.claude/skills/branch-recap/SKILL.md` line 35 and 75: the script runs the worker itself; the receipt no
   longer hands the user a command.

#### Automated Verification

- `python3 tests/parallel_tests.py test_stage_run.py test_ledger_deferred.py` passes.

## Phase 4: refactor_flow log accepts a simplify target the branch deleted

File: `claude/.claude/skills/refactor/scripts/refactor_flow.py` (`check_targets_match`), tests in
`tests/scripts/test_refactor_flow.py`.

A simplify fix that deletes a slice file and stages the deletion makes `log` exit 1 ("matches no tracked file"), so the
caller drops the path and the logged target no longer matches the slice that ran.

1. `check_targets_match` accepts a target that matches no file in the index when it matches a file at `HEAD`
   (`git ls-tree -r --name-only HEAD -- <target>`). It prints one line naming the target as deleted. A target in
   neither still raises the current error.

#### Automated Verification

- New tests: a target whose file is deleted and staged is accepted and printed as deleted; a target never tracked is
  still refused.
- `python3 tests/parallel_tests.py test_refactor_flow.py` passes.
