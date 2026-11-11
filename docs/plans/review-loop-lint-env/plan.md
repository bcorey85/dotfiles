# Review loop: lint every changed file, formatting-only hunks, personal gate env

Repo: ~/dotfiles (direct-edit). Three independent script fixes in the review loop's helpers. Do not edit `review/review_loop_prompts.py`, `review/review_fix.py`, `review/review_fix_asks.py`, `skills/`, `tools/pipe_shell_check.py` or `tools/pull_keep_index.py`: other lanes own them. `review/review_loop_script.py` is over 1000 lines: add no route, verb or state field to it; Phase 3 may change one message string there.

## Phase Status

- [x] Phase 1: the full-check pass fails on lint left in any changed file (risk: medium)
- [x] Phase 2: the removed-change guard ignores formatting-only hunks (risk: low)
- [x] Phase 3: gate env from a personal per-repo file (risk: low)
- [ ] Phase 4: the relay sends a stop back for review when the tree changed after the converged review (risk: low)

## Phase 1: the full-check pass fails on lint left in any changed file

Queue item: `~/agent-evals/queue/review-loop-lints-source-files-but-not-the-branch.md`.

Today the loop's format step (`lib/format_files.py` `run_formatters`, called from `review_loop_script.format_reviewed_files` and `full_check_gate.autofix_touched_files`) runs `ruff check --fix` and `oxlint --fix` / `eslint --fix` and ignores their exit codes. Violations with no autofix (ruff RUF012, N802, B023, E501) stay in the tree, the review converges, and pre-commit refuses the commit. This hits test files and source files alike.

Changes:
- `lib/format_files.py`: add `lint_problems(repo, paths)` (no `check_command`: nothing reads it). It runs the same linters `run_formatters` would pick for those paths with `configured_only=True` (reuse the same selection code; one owner for which tool runs on which file), in check mode with no fix: `ruff check --force-exclude --output-format concise <python files>` when ruff is on PATH and the repo configures ruff; `oxlint <files>` or `eslint --no-warn-ignored --max-warnings=0 <files>` when the repo configures that tool and it is installed (local `node_modules/.bin` or PATH; no `npx` install). It returns a list of `(command text, output)` for each linter that exited non-zero, `[]` when all pass or no linter applies. Skip `docs/plans/` and prompt markdown as `run_formatters` does. A linter that cannot start (missing binary) is not a problem.
- `review/full_check_gate.py` `FullCheckSteps.full_check_pass`: before running the check, call a new `lint_pass()` on `sorted(set(self.review_scope()) | self.files_touched)` (the host provides `review_scope`). When `lint_problems` returns any, send one coder repair (`self.repair("coder-lint", records)`, records built with `parse_finding` from a finding text that holds each command and its output), `mark_repaired`, re-run `run_formatters` on those files, then `lint_problems` once more. Still failing → `self.stop("critical-blocker", ["lint still failing after one repair:\n" + output])`, and `full_check_pass` returns without running the check.

#### Automated Verification
- New tests in `tests/scripts/test_format_files.py`: a temp repo with `ruff.toml` and a test file `tests/test_x.py` holding an unfixable violation (for example a function named `testCamel` under `select = ["N802"]`) → `lint_problems` returns one ruff entry naming the file; a clean file → `[]`; a repo with no ruff config → `[]`. Skip the test when ruff is not on PATH. The first case fails before the change (no such function).
- New test for `full_check_pass` (in the existing test file that covers `FullCheckSteps`, or `tests/scripts/test_review_loop_script.py`): with `lint_problems` stubbed to return a problem twice, the pass stops `critical-blocker` with the lint text and the check command never runs; stubbed to return a problem then `[]`, one repair runs and the check runs.
- `bash tests/run.sh` passes.

## Phase 2: the removed-change guard ignores formatting-only hunks

Queue item: `~/agent-evals/queue/code-review-loop-gate-env-and-churn-revert-false.md` (second half).

`lib/change_removal.py` `added_lines` counts every line the new text holds that the old text lacks. When the change under review reflowed base lines (formatter churn) and a fix pass reverts the churn, the guard counts the reflowed lines as removed work and stops the phase with `ChangeRemovedError`.

Change: `added_lines(old_text, new_text)` leaves out the lines of every hunk whose only change is formatting. Diff the two line lists with `difflib.SequenceMatcher` (autojunk off); for each `replace` opcode, compare the normalized old block with the normalized new block, and when they are equal, those new lines are not added. Normalize a block by joining its lines, dropping all whitespace, turning `'` into `"`, and dropping a `,` that comes right before `)`, `]` or `}`. `insert` opcodes and `replace` hunks with a real change count as today (the existing Counter semantics for the non-formatting lines stay). Update the module docstring.

#### Automated Verification
- New tests in `tests/scripts/test_change_removal.py`: a base call `f(a, b)` reflowed to `f(\n    a,\n    b,\n)` gives no added lines; a reflow that also changes a name (`f(a, c)`) still counts; quote-only change gives none; the existing tests still pass. A test that a change adding 12 reflowed lines plus a fix pass that reverts them is not `is_gutted` (through `removed_by_file`). The reflow case fails before the change.
- `bash tests/run.sh` passes.

## Phase 3: gate env from a personal per-repo file

Queue item: `~/agent-evals/queue/code-review-loop-gate-env-and-churn-revert-false.md` (first half).

The gate env reaches the loop only from the plans' Automated Verification commands (`lib/plan_format.py` `repo_gate_env`). A repo whose CI sets a test env var that no plan names gets scoped test runs without it, and the loop stops on errors that are not the change's. The toolkit never adds a file to a company repo, so the per-repo env lives in a personal file.

Changes:
- `lib/plan_format.py` `repo_gate_env(repo_root, plan_rel=None)`: merge assignments from the personal file `~/.claude/gate-env.json` (path overridable with env var `CLAUDE_GATE_ENV_FILE`, for tests). Shape: `{"<repo name>": ["NAME=value", ...]}`. The repo name is the last path part of `git remote get-url origin` without `.git`; with no origin, the main worktree folder name (`git rev-parse --path-format=absolute --git-common-dir`, parent folder). A plan's assignment wins over the file's for the same name. A missing file is no assignments. A file that is not valid JSON, or not that shape, or holds a word that is not a literal NAME=value (`script_utils.ENV_ASSIGNMENT`): raise `ValueError` naming the file and the bad entry (loud failure; `code_review_start.py` lets it surface).
- `review/review_loop_script.py`: the scoped-tests `critical-blocker` text (line ~909) gains one line after the tails: the line names the repo's actual key and the personal file path in use (`plan_format.gate_env_repo_name`, `plan_format.personal_gate_env_file`-style path). No other change to that file.

#### Automated Verification
- New tests in `tests/scripts/test_plan_format.py`: a temp repo with origin `git@x:org/app.git` and a gate-env file `{"app": ["PLUGINS=1"]}` → `repo_gate_env` holds `PLUGINS=1`; a plan that sets `PLUGINS=0` wins; a missing file adds nothing; a malformed file raises `ValueError` naming the file. The first case fails before the change.
- `tests/scripts/test_code_review_start.py` still passes; add one case that the prompt's `gate-env:` line carries the file's assignment.
- `bash tests/run.sh` passes.

## Phase 4: the relay sends a stop back for review when the tree changed after the converged review

Queue item: `~/agent-evals/queue/code-resume-edits-reviewed-code-without-re-review.md`.

A /code fork that edits reviewed source after its review loop converged (a resume applying the user's rulings, or the accepted-asks coder) ends on a phase-complete stop. The tree no longer matches the converged hand-back's tree, so review-commit-gate denies the commit and the main session runs a second full /review. The gate is right; the run never re-reviewed the edit.

Changes:
- `code/code_relay.py` `relay(repo)`: before it relays a stop that waits on the user (`waits_on_user`), it reads the session's latest hand-back for the repo's top level through `handback_store.latest_for_repo(os.environ["CLAUDE_CODE_SESSION_ID"], top)` (no session id in the environment → skip the check). When that hand-back is clean (`handback.standing_false_clean_reason(seen)` is None), was stored after the HEAD commit's committer time (`git log -1 --format=%ct`; so a commit since the review skips the check), and `reviewed_tree.is_reviewed(session, repo)` is False, it does not relay: it exits 0 with a rule that tells the main session to run the stop's `To go on:` line with the feedback `Re-run the phase review (step 5) on the current tree: files changed after the review converged.`, and leaves `relayed` unwritten so the next relay of the new stop works. Every other case relays as today. Use the owners named in `scripts/CLAUDE.md`; add no fingerprint or clean-status logic.
- Module docstring: one sentence on the new case.

#### Automated Verification
- New tests in `tests/scripts/test_code_relay.py` (temp repo with one commit, `HOME` and `CLAUDE_CODE_SESSION_ID` pointed at temp values): a stored clean hand-back whose tree is the current tree → relays as today; a source edit after that hand-back → exit 0, the output names the re-review feedback and holds no USER TEXT markers, and `relayed` is not written; a notes-path edit (`docs/plans/x.md`) after it → relays; a commit after the hand-back → relays; no session id → relays. The source-edit case fails before the change.
- `bash tests/run.sh` passes.

## Plan Deviations

Phase 1: lint_problems drops the unused check_command parameter; adopted by the session, 2026-11-10; no acceptance criterion changes.
Phase 2: a reflow next to a real edit in the same replace hunk still counts as added (whole-hunk comparison kept as the plan says); decided by the session, 2026-11-10; no acceptance criterion changes.
Phase 3: the personal file's words must match script_utils.ENV_ASSIGNMENT (literal NAME=value) and the stop hint names the actual repo key and file; adopted by the session, 2026-11-10; no acceptance criterion changes.
