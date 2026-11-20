# Test env and commands: the gates that pick and run a repo's checks

Fix fourteen queued toolkit defects in the gates that pick and run test, lint and suite commands. Each phase starts with
a test that fails on the current tree. Scripts live in `claude/.claude/scripts/` (paths below are relative to it unless
they start with `scripts/` or `tests/`); tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`. Follow
`docs/toolkit-script-rules.md` and `claude/.claude/scripts/CLAUDE.md` (owners, no second copy of a fact).

## Scope

- In: `lib/gate_env.py`, `review/full_check.py`, `review/full_check_gate.py`, `review/review_loop_main.py` (only
  `build_loop`'s check command), `code/coder_gate.py`, `code/gate_commands.py`, `code/check_discovery.py`,
  `tools/criteria_dry_run.py`, `lib/check_output.py`, `gates/quality_check_cap.py`, `review/verify-prep`,
  `scripts/.local/bin/herdr-worktree`, their tests.
- Out: the review loop's finding skip, scope and closure code (another lane); `review_fix.py` asks code and
  `review-commit-gate` (other lanes); prompt files under `claude/.claude/agents/` and `claude/.claude/skills/`.
- Dropped in triage (one sighting, one repo, no wrong record): the Rust job cap and pause item, the pre-commit eslint
  item, the plan fixture port item. The hand-back item's "coder writes no placeholder file" clause is a prompt rule
  that a hook already blocks; cut, see Plan Deviations.

## Phase Status

- [x] Phase 1: one check env for every gate: the main checkout's pyenv pin, and herdr-worktree links `.python-version` (risk: medium)
- [x] Phase 2: a lock-file runner that is not installed falls back to the project venv, and a missing tool is named as an environment gap (risk: medium)
- [x] Phase 3: the discovered full check runs only the parts the change touches, each on its own (risk: medium)
- [x] Phase 4: a test database collision is retried and never counted as a code failure (risk: medium)
- [x] Phase 5: a test command given on resume replaces the default full check (risk: medium)
- [x] Phase 6: failing-test lines skip log lines, and traceback line numbers do not hide a pre-existing failure (risk: low)
- [x] Phase 7: quality-check cap keys on the env prefix and lets a run with no runner output rerun (risk: low)
- [x] Phase 8: gate commands carry no `cd` chain, and cargo runs only for changed Rust files (risk: medium)
- [x] Phase 9: verify-prep run rules keep the default TMPDIR for test runs (risk: low)

## Phase 1: one check env for every gate

Bug: in a fresh worktree the gitignored `.python-version` is missing, and only `full_check.run` puts the pyenv shims on
PATH (`full_check.pinned_interpreter_env`, only when the worktree itself has the file). `coder_gate.run_commands`,
`scoped_run`, `run_hit_check` and `criteria_dry_run` run with plain `os.environ`, so `pipenv run ...` exits 127.

Fix:

- Move `pinned_interpreter_env` into `lib/gate_env.py` as `check_env(repo, env=None)` and delete it from
  `full_check.py`. It returns a full env dict. The pin is `<repo>/.python-version`, else the main checkout's
  (`git rev-parse --path-format=absolute --git-common-dir`, parent folder). When the pin comes only from the main
  checkout, set `PYENV_VERSION` to the file's first non-empty line. When a pin is found and `$PYENV_ROOT/shims`
  (default `~/.pyenv/shims`) is a folder, put it first on PATH. No pin: env unchanged.
- Callers use it: `full_check.run`, `coder_gate.run_commands`, `coder_gate.scoped_run`, `coder_gate.run_hit_check`
  (the gate's own `NAME=value` words go on top), `criteria_dry_run` (pass `env=` to `script_utils.run_command`).
- Name `check_env` as the owner of the check env in `lib/gate_env.py`'s docstring (the scripts CLAUDE.md is not
  edited in this lane).
- `scripts/.local/bin/herdr-worktree`: right after the workspace id check and before the node install loop, when
  `$main_checkout/.python-version` exists, `$worktree/.python-version` does not, and
  `git -C "$worktree" check-ignore -q .python-version` succeeds, symlink it into the worktree and print one line. A
  tracked or non-ignored file is left alone so `git status` stays clean.

Tests: `test_gate_env.py`: a linked worktree with the pin only in the main checkout gets `PYENV_VERSION` and the shims
first; a worktree with its own pin gets no `PYENV_VERSION`; no pin anywhere leaves PATH alone (the full_check pinned-env
tests move here). `test_coder_gate.py` and `test_criteria_dry_run.py`: a fake `pipenv` placed only in a fake
`$PYENV_ROOT/shims` runs when the main checkout pins a version. `test_herdr_worktree.py`: the ignored file is linked and
`git status --porcelain` is empty; a non-ignored one is not linked.

**File**: `claude/.claude/scripts/lib/gate_env.py`, `claude/.claude/scripts/review/full_check.py`, `claude/.claude/scripts/code/coder_gate.py`, `claude/.claude/scripts/tools/criteria_dry_run.py`, `scripts/.local/bin/herdr-worktree`
**Test**: `tests/scripts/test_gate_env.py`, `tests/scripts/test_coder_gate.py`, `tests/scripts/test_criteria_dry_run.py`, `tests/scripts/test_herdr_worktree.py`

## Phase 2: a lock-file runner that is not installed falls back to the project venv

Bug: `gate_commands.project_python_runner` returns `["pipenv", "run"]` whenever `Pipfile.lock` exists (same for uv,
poetry, pdm), without checking the tool is installed, and never falls back to `.venv`/`venv` (`linked_installs.
VENV_FOLDERS`). `check_discovery.python_part_commands` uses it too. A 127 then reads as a bare `setup fault (exit 127)`
in the full check, a `setup-fault` stamp naming no tool in the hand-back gate, and BROKEN in the criteria dry run.

Fix:

- `project_python_runner(repo_dir)`: use a lock-file runner only when `shutil.which(runner[0],
  path=<PATH of gate_env.check_env(repo)>)` finds it; else fall to the existing venv branch. When neither exists, keep
  the lock-file runner (so the run names the missing tool).
- `lib/check_output.py`: one function `missing_tool(code, output)` returning the tool name from a shell `command not
  found` line or a pyenv `<tool>: command not found` line when the exit is 127, else None, and `missing_tool_text(code,
  output)` returning `<tool> not found on PATH` for the three sites below.
- `full_check.failed_run_result`: exit 127 with a named tool gives `not run (environment gap: <tool> not found on
  PATH)`, through the same path as the existing `environment_gap`, never a test failure.
- `coder_gate`: the setup-fault stamp line names the tool (`setup fault: <command> (<tool> not found on PATH)`). It
  stays non-blocking and uncounted.
- `criteria_verdict.item_verdict` (in `lib/criteria_verdict.py`; the dry run calls it): rc 127 with a named tool gives ENV with `fix: install <tool> or add the pyenv
  shims to PATH`, not BROKEN.

Tests: `test_gate_commands.py`: `Pipfile.lock` plus `.venv/bin/python` and no pipenv on PATH gives the venv runner;
pipenv on PATH keeps `pipenv run`. `test_check_output.py`: `missing_tool` on bash, zsh, sh and pyenv shapes.
`test_full_check.py`, `test_coder_gate.py`, `test_criteria_dry_run.py`: a 127 run names the tool and is not a failure.

**File**: `claude/.claude/scripts/code/gate_commands.py`, `claude/.claude/scripts/lib/check_output.py`, `claude/.claude/scripts/lib/criteria_verdict.py`, `claude/.claude/scripts/review/full_check.py`, `claude/.claude/scripts/code/coder_gate.py`, `claude/.claude/scripts/tools/criteria_dry_run.py`
**Test**: `tests/scripts/test_gate_commands.py`, `tests/scripts/test_check_output.py`, `tests/scripts/test_full_check.py`, `tests/scripts/test_coder_gate.py`, `tests/scripts/test_criteria_dry_run.py`

## Phase 3: the discovered full check runs only the parts the change touches, each on its own

Bug: `check_discovery.part_commands_check` joins the package and Python part commands with `&&` and ignores the
changed paths. A frontend-only phase runs the backend suite; a 127 in the backend part skips the frontend part.

Fix: `discovered_check_command` (and `part_commands_check`) take the changed paths. A part runs only when a changed
path has its path kind (the package part owns JS/TS/CSS/HTML/JSON/package.json paths, the Python part owns `.py` and
Python config paths); a changed path of neither kind (root config, lock file, CI), or no changed paths, runs every
part. Parts are joined
so each runs whatever the earlier one exited, and the run fails when any part failed (reuse the `FAILED: <steps>` form
`full_check` already parses, or run the parts as separate steps; pick the one `full_check` reads today). The full
check passes the diff's changed paths (it already has `repo` and `base`). A repo's own `Quality check:` line is run as
written, unchanged. A part that exits 127 is an environment gap (Phase 2); the other parts still give a result.

Tests: `test_check_discovery.py` (or the file that tests it today): a frontend-only change gives only the package
part; a backend-only change only the Python part; a root config change both. `test_full_check.py`: a backend part that
exits 127 still runs the frontend part, and the result names the gap and the frontend result.

**File**: `claude/.claude/scripts/code/check_discovery.py`, `claude/.claude/scripts/review/full_check.py`
**Test**: `tests/scripts/test_check_discovery.py`, `tests/scripts/test_full_check.py`

## Phase 4: a test database collision is retried and never counted as a code failure

Bug: parallel worktrees run `manage.py test --noinput` against the same default test DB name; one run drops the
other's DB. The hand-back gate counts it as a failed attempt; the full check reads it as a blocker. Django has no env
var for the test DB name, so the toolkit cannot pick one per worktree without the repo's settings.

Fix: `lib/check_output.py` gains `is_test_db_collision(output)`: Django's `Got an error recreating the test database`,
Postgres `database "test_..." is being accessed by other users`, `database "test_..." does not exist` mid-run,
`InvalidCatalogName`, MySQL/SQLite equivalents only if a real shape is known. `coder_gate.run_commands` and
`full_check.run`: on a collision, wait (30 s) and run the command once more; a second collision is a setup fault
naming the collision and the fix (`set DATABASES TEST NAME from an env var and add it to ~/.claude/gate-env.json`),
never a counted failure or blocker.

Tests: `test_check_output.py`: each collision shape matches; an ordinary failing test with a DB word does not.
`test_coder_gate.py`: a command that collides once then passes gives a pass and no attempt counted; one that collides
twice gives a setup fault, uncounted. `test_full_check.py`: same for the full check.

**File**: `claude/.claude/scripts/lib/check_output.py`, `claude/.claude/scripts/code/coder_gate.py`, `claude/.claude/scripts/review/full_check.py`
**Test**: `tests/scripts/test_check_output.py`, `tests/scripts/test_coder_gate.py`, `tests/scripts/test_full_check.py`

## Phase 5: a test command given on resume replaces the default full check

Bug: `review_loop_main.build_loop` always takes `full_check.configured_check_command`; a `--test` only adds a scoped
gate command. A resume after a setup fault, given a runnable `--test`, stops on the same fault
(`full_check_gate.full_check_pass` → `stop_on_setup_fault`), and the commit gate then has no converged review.

Fix: when the launch request carries `--test` commands and the session's previous hand-back for this repo (read
through `handback_store.latest_for_repo`) stopped as `setup-fault`, `build_loop` sets the full check to the `--test`
commands and the loop records `check_overridden: true`. `full_check_pass` and `recheck_full_check` never call
`stop_on_setup_fault` for the overridden default check. A `--test` on any other launch stays a scoped gate.

Tests: `test_review_loop_script.py`: a resume after a recorded setup fault with `--test 'cmd'` runs `cmd` as the full
check and converges; a plain launch with `--test` keeps the configured full check; a resume after a run with no setup
fault is unchanged.

**File**: `claude/.claude/scripts/review/review_loop_main.py`, `claude/.claude/scripts/review/full_check_gate.py`
**Test**: `tests/scripts/test_review_loop_script.py`

## Phase 6: failing-test lines skip log lines; traceback line numbers do not hide a pre-existing failure

Bug 1: `check_output.FAILING_TEST_LINE` matches logger lines (`ERROR django.request ...`, `ERROR: some message`), so
the packet lists log noise as failing tests and the cap of 20 drops the real one. Fix: the unittest branch needs the
test-header shape `^(?:FAIL|ERROR): \w+ \([\w.]+\)`; the pytest branch needs a node id or path (`^(?:FAILED|ERROR)
\S+(?:::\S+)?(?: - |$)` with `::` or a `/` or `.py`). Keep every other existing branch.

Bug 2: a scoped failure that fails the same way on base still stopped the loop when the diff shifted lines in the
test file: `File ".../test_api.py", line 3405, in test_export` vs `line 3397`. Fix: `normalized_log_line` strips the
line number from a Python traceback frame line, as it does for Rust panic lines.

Tests: `test_check_output.py`: log lines beside a real `FAIL: test_x (a.B)` give only the real one; pytest
`FAILED tests/x.py::t - ...` still matches. `test_full_check.py`: a head and base log that differ only in a frame's
line number read as pre-existing (fixture copied from the planbench T024827 scoped logs, trimmed).

**File**: `claude/.claude/scripts/lib/check_output.py`
**Test**: `tests/scripts/test_check_output.py`, `tests/scripts/test_full_check.py`

## Phase 7: quality-check cap keys on the env prefix and lets a run with no runner output rerun

Bug: `gates/quality_check_cap.py` strips leading `NAME=value` words before it builds the run key, so a rerun that only
adds an env prefix is denied as "re-running unchanged code". A failed run that printed no runner output is recorded
like a real result. (Exit 126/127 already records nothing.)

Fix: keep the leading assignment words in the key (still use the stripped segment for `is_check`). In the failure
branch, skip recording when `check_output` says the runner could not start, or an environment fault with no runner summary
(`test_run_output` / `check_output` owners; no new regex).

Tests: `test_quality_check_cap.py`: `FOO=1 pytest x` after a recorded `pytest x` is allowed; a failed run with only a
traceback from import (no runner summary) records nothing.

**File**: `claude/.claude/scripts/gates/quality_check_cap.py`
**Test**: `tests/scripts/test_quality_check_cap.py`

## Phase 8: gate commands carry no `cd` chain; cargo runs only for changed Rust files

Bug 1: `gate_commands.in_directory` emits `cd <dir> && <cmd>`, which the worktree shell rule forbids. Fix: emit one
simple command with the tool's own folder flag: `pnpm -C <dir> ...`, `npm --prefix <dir> ...`, `yarn --cwd <dir>
...` (manager from `gate_commands.package_manager`), `npm --prefix <dir> exec -- <bin> ...` for npx-style tools,
`cargo ... --manifest-path <dir>/Cargo.toml`. `{files}` paths stay right for the folder the command runs in.
`coder_gate.command_directory` reads the new flags as well as `cd` (plan-listed commands still use `cd`); update
`check_scope`'s folder tracking where a gate command stopped using `cd`.

Bug 2: `gate_commands.cargo_commands` adds the crate's clippy and test entries for a `.py` or `.md` file inside a
crate folder. Fix: skip non-Rust files before grouping by crate, so no changed Rust file gives no cargo command.

Tests: `test_gate_commands.py`: no emitted command contains `cd ` or `&&`; a pnpm package gives `pnpm -C`; a diff with
only `.py`/`.md` under a crate gives no cargo command. `test_coder_gate.py`: `{files}` resolves for `pnpm -C`.

**File**: `claude/.claude/scripts/code/gate_commands.py`, `claude/.claude/scripts/code/coder_gate.py`, `claude/.claude/scripts/lib/check_scope.py`
**Test**: `tests/scripts/test_gate_commands.py`, `tests/scripts/test_coder_gate.py`

## Phase 9: verify-prep run rules keep the default TMPDIR for test runs

Bug: `review/verify-prep` `VERIFIER_RUN_RULES` rule 4 says redirected output goes only under the verify-output folder
inside the git dir and "never write it to /tmp"; the verifier set TMPDIR there, and tests that build temp repos broke.
Fix: rule 4 says redirected output goes only under `{output_dir}`, and test runs keep the default TMPDIR: never set
TMPDIR.

Tests: the verify-prep test file: the printed run rules name TMPDIR and say to keep the default.

**File**: `claude/.claude/scripts/review/verify-prep`
**Test**: `tests/scripts/test_verify_prep_queue_ticket.py`

## Plan Deviations

- 2026-11-19, session agent-evals-5e (criteria written by a session): the hand-back item's placeholder-file Done-when
  is cut; a hook blocked the write, one sighting. The item closes on the pipenv fallback.
- 2026-11-19: the `base_run` parameter rename (`gate_env` to `gate_assignments`) also edited `full_check_gate.py`
  (adopted plan impact, no criterion changed).
- 2026-11-19: ruling by the code session on AC5: discovery only finds root-rooted parts, so "parts whose folders hold a
  changed path" is read as path kind inside the root (package part: JS/TS/CSS/HTML/JSON; Python part: `.py` and Python
  config; neither kind runs every part).
- Subfolder pin for own_pin_exists: skipped, no session reported one (toolkit-script-rules Size); ruled by the orchestrating lane, 2026-11-19
- ruling, none (no AC), code session, 2026-11-19: Phase 4 matches Django's "recreating" line, not "creating"
- ruling, AC7, code session, 2026-11-19: --test replaces the default full check only after a setup fault on the previous run, not on every launch (the any-launch form breaks the scoped-gate flow, 7 existing tests)
- 2026-11-19, ruled by the orchestrating session (owner plan): AC7 widens to "a `--test` replaces the default full check after a setup fault or after an overridden run (`check_overridden` is recorded in the packet); on any other launch it stays a scoped gate"; and a setup fault in the overriding `--test` command itself stops the loop as `setup-fault`.
- 2026-11-19, ruled by the orchestrating session (owner plan): Phase 6 applies the strict header/node-id shape to `ERROR` lines only (`FAIL:`/`FAILED` keep old matching), no AC change; AC9 covers the Python `File "...", line N` traceback form only, pytest `path.py:N:` location lines are not stripped (no session hit them; toolkit rule: no code for a shape nobody hit).
- 2026-11-19, ruled by the orchestrating session (owner plan): AC10 narrows to "a failed run whose output shows the tool could not start, or an environment fault with no runner summary, is not recorded"; a literal no-summary rule would stop recording failed ruff/eslint/mypy runs.
- 2026-11-19: Phase 8 Bug 2 (cargo entries for non-Rust files) already held before the phase; kept as a regression test.
- 2026-11-19, ruled by the orchestrating session (owner plan): npm subfolder binary commands are not emitted because `npm --prefix <dir> exec` runs in the caller's cwd, not `<dir>`; AC11 narrows for npm to scripts only (`npm --prefix <dir> run/test`); pnpm `-C` and yarn `--cwd` binary commands stay.
- 2026-11-19: asks rejected: discovery's bare `yarn <tool>` form is out of Phase 8 scope.
- 2026-11-19, lane session (criteria written by a session): branch review asks 7-10 taken as proposed; Phase 5 also
  fires after an environment-gap hand-back.

- 2026-11-19: Adopt plan change. Ruled by the session, not the user at 2026-11-19 07:50.

  The ruling: the loop narrows by its review base, re-resolved at check time (asks 3, 4); ruled by: dotfiles-test-env-and-commands

  The disagreement:
  claude/.claude/scripts/review/full_check.py:415 [plan-drift] — PLAN-IMPACT: AC5 says the discovered full check runs only the parts the change touches. The review loop never narrows: `build_loop` calls `configured_check_command(repo)` with no base. `full_check_gate.run_full_check` passes no `base` to `full_check.run`. `run` now defaults `base=None`, so every part runs. The old default was `"HEAD"`. Only close-branch's CLI call with `--base` narrows. Nothing in production reaches `narrowed_discovered_command`: the CLI's `main` already narrows through `configured_check_command(args.repo, args.base)`, and the loop passes no base. The fix note also says "`review/full_check.py` passes the diff's changed paths", and that is false for the loop. Question: should the review loop's full check narrow to the diff (pass the loop's base, HEAD for the working-tree change, through `run_full_check`), or is narrowing meant for close-branch only? Change if accepted: pass the base from `full_check_gate.run_full_check` into the runner, so `narrowed_discovered_command` becomes live. If rejected: delete `narrowed_discovered_command` and correct the note and changelog line. acceptance_criteria: AC5

- 2026-11-19 08:50, ruled by the session (criteria written by a session); ruled by: dotfiles-test-env-and-commands. Refactor-review asks: (1) modified: pass the run env into `project_python_runner` (`check_env(repo, env)`), and `coder_gate.command_directory` takes the npm `--prefix … exec` folder from the one `check_scope` owner (exec runs in the caller's cwd); (2) accepted: the mid-run collision shape (every failing unittest block holds the collision text) counts as a collision (AC6), with real unittest output as the fixture; (3) rejected: no session hit the pyenv shim case; the AC4 environment-gap report covers it.
- 2026-11-19 09:40, ruled by the session; ruled by: dotfiles-test-env-and-commands. Round-2 ask (quality_check_cap per-check no-result verdict for mixed `;` commands): rejected; no session hit a mixed command (toolkit rule: no code for a shape nobody hit).
