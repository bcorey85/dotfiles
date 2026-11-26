# Criteria dry run: true ENV and RED labels, every phase listed

Fix four queued defects of `claude/.claude/scripts/tools/criteria_dry_run.py`. Each phase starts with a test that
fails on the current tree. Tests live in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

The rule for every label: a check that could not run reads ENV; a check that ran and failed reads RED.

## Scope

- In: `lib/check_output.py`, `lib/criteria_verdict.py`, `tools/criteria_dry_run.py`,
  `skills/eng-spec/phases/6-finalize.md` (the printed label list), and the tests of each.
- Out: `review/review_loop_scope_guard.py`, `review/review_launch.py`, `lib/memory_cap_scope.py` (the cap already
  wraps every dry-run command: `CappedRunTest` in `tests/scripts/test_criteria_dry_run.py` pins it).

## Phase Status

- [x] Phase 1: environment failures read ENV and an "exits 0" search reads RED on no match (risk: medium)
- [ ] Phase 2: the dry run lists closing-phase checks (risk: low)

## Phase 1: environment failures read ENV and an "exits 0" search reads RED on no match

Real outputs from the bench runs under `~/dev/evals/noresearch1/runs/*/tree` and from transcripts:

- vitest whose setup file throws an env guard: `Error: Refusing to run the test suite — the environment does not look
  disposable:` then `  - DATABASE_URL is not set` lines, `Test Files  1 failed (1)`, `Tests  no tests`, rc 1. Read RED
  today.
- prisma with no `DATABASE_URL`: `error: Environment variable not found: DATABASE_URL.`, rc 1. Read RED today.
- Django with Postgres down: `django.db.utils.OperationalError: connection to server at "127.0.0.1", port 5432
  failed: Connection refused`, no runner summary. Read RED today.
- npm script whose binary is missing, with bash as `/bin/sh`: `sh: line 1: tsc: command not found`, rc 127. Read
  BROKEN today: `missing_tool` knows only `/bin/sh: line N:`.
- `` `rg -q A f && rg -q B g` exits 0. `` at rc 1. Read GREEN today: "exits 0" is not presence wording, so the line
  reads as a ban.

1. `check_output.py`: the `/bin/sh: line N:` not-found branch also takes `sh: line N:`, so `missing_tool` names the
   program.
2. `check_output.py`: one named pattern constant owns the environment-gap forms: an unset variable line
   (`<NAME> is not set`, `Environment variable not found: <NAME>`) and a refused connection (`connection to server at
   ... failed: Connection refused`, `ECONNREFUSED`, prisma's `Can't reach database server`). A new function returns
   the first such line of a failed run whose output holds no runner summary (`test_run_output.runner_summaries`), else
   None. A run with a runner summary ran tests and stays RED.
3. `criteria_verdict.item_verdict`: when `cannot_start_line` gives nothing, that new line reads ENV with the flag
   `environment failure: <line>`.
4. `criteria_verdict.PRESENCE_WORDING` takes `exit(s) 0` and `exit code 0`, so such a search reads RED at rc 1. Ban
   wording on the same line still wins.

#### Automated Verification

- Fixtures from each real output above in `tests/scripts/test_check_output.py` and
  `tests/scripts/test_criteria_verdict.py`: the vitest env guard, the prisma unset variable and the Django refused
  connection read ENV; a vitest run that reports `Tests  2 failed` beside an `is not set` line stays RED; the npm
  `sh: line 1: tsc: command not found` at rc 127 reads ENV naming `tsc`; the "exits 0" rg compound at rc 1 reads RED.
- `python3 tests/parallel_tests.py test_check_output.py test_criteria_verdict.py test_criteria_dry_run.py` passes.

## Phase 2: the dry run lists closing-phase checks

Bug: the bench plan's `Phase 4: Close pass` checks left the report with no line, so a reader could not tell they
exist. A closing phase runs its own skill, so its checks are not run here.

1. `criteria_dry_run.py`: each Automated Verification item of a closing phase prints `CHECK <label> CLOSING <skill>
   <command or item text>` and is not run. It needs no answer: the exit code is unchanged.
2. `skills/eng-spec/phases/6-finalize.md`: the printed label list names `CLOSING`.

#### Automated Verification

- `tests/scripts/test_criteria_dry_run.py`: the closing-phase test asserts the item is listed as CLOSING, not run,
  and the run still exits 0.
- `python3 tests/parallel_tests.py test_criteria_dry_run.py` passes.

## Final

- `bash tests/run.sh` passes under the memory cap.

## Plan Deviations
