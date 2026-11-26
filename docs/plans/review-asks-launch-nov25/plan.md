# Review asks and launch batch: full check log folder, /review carries the plan, inline hint names the scratchpad

Fix three queued toolkit defects. Each phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

Queue item `review-asks-done-takes-only-by-user-so-a-lane` is dropped: `asks-done --by session` has existed since
999f519ec (2026-11-11) and releases a plain ask; the only asks it refuses are `user_only` ones (user-owned criteria or
an approval-only file), which only the user rules under the global acceptance-criteria rule. See `03-decisions.md`.

## Scope

- In: `review/full_check.py`, `review/review_launch.py`, `review/review_loop_prompt_file.py`,
  `gates/inline_interpreter_hint.py`, `skills/review/SKILL.md` (one flag line), and the tests of each.
- Out: `review/review_fix_asks.py` and the asks-done verb; `bash-safety-gate.sh` (generated); every CLAUDE.md,
  `orchestration.md` and `settings.json`.

## Phase Status

- [x] Phase 1: full_check makes the log's missing folder (risk: low)
- [x] Phase 2: a /review launch carries the plan and its decision log (risk: medium)
- [x] Phase 3: the inline-interpreter deny names the session's scratchpad file first (risk: low)

## Phase 1: full_check makes the log's missing folder

Bug: `full_check.py <repo> --log <dir>/x.log` with `<dir>` missing raised FileNotFoundError from
`run_check_command`'s `open("w")` after the receipt row was written, so the wait was wasted.

1. `run_check_command`: create the log's parent folders (`mkdir(parents=True, exist_ok=True)`) before it opens the
   log. Every caller of `run` gets it.

#### Automated Verification

- [x] **Missing log folder**: a --log under a missing folder runs the check and writes the log - `python3 tests/parallel_tests.py test_full_check.py`

## Phase 2: a /review launch carries the plan and its decision log

Bug: a /review launch on a lane branch named no plan, so its reviewers never saw the plan's recorded rulings and
filed three asks that repeated them.

1. `review_launch.py`: a `--plan <path>` flag (absolute, or relative to the repo root). With no flag, the plan path
   from the repo's code-phase record (`code_wait.read_phase_run(repo)["plan"]`), when that file exists inside the
   repo. The launch writes `plan: <repo-relative path>` into the prompt header, so the loop gets the plan as a /code
   phase review does. A `--plan` that is not a file inside the repo stops the launch with one line.
2. `review_loop_prompt_file.reviewer_brief`: when the plan's folder holds `03-decisions.md`, the reviewer may open it,
   and the brief says a question a recorded ruling there or in the plan answers is not an ask.
3. `skills/review/SKILL.md`: `plan=<path>` maps to `--plan <path>`.

#### Automated Verification

- [ ] **Launch plan header and brief**: a code-phase record's plan reaches the header; a 03-decisions.md file reaches the brief - `python3 tests/parallel_tests.py test_review_launch.py test_review_loop_prompt_file.py`

## Phase 3: the inline-interpreter deny names the session's scratchpad file first

Bug: one session hit 27 inline-interpreter denies; each deny text opened with what is blocked and named the
scratchpad only in general words.

1. `gates/inline_interpreter_hint.py`: the deny text starts with the route. When the payload's `transcript_path` and
   `session_id` give an existing scratchpad folder
   (`<claude code temp root>/<project slug>/<session id>/scratchpad`), the text names that folder as the place to
   write the script; otherwise it keeps the general words.

#### Automated Verification

- [x] **Scratchpad route first**: the deny names the session scratchpad when it exists - `python3 tests/parallel_tests.py test_inline_interpreter_hint.py`
- [x] **Suite**: the whole suite passes - `bash tests/run.sh`
