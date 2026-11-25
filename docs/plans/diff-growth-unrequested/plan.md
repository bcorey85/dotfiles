# Diff growth: the docs, tests and code split at the close pass

The close pass reports the branch's added lines split into docs, tests and code, and flags a docs or tests part that
passes a set share of the branch. Scripts live in `claude/.claude/scripts/`; tests in `tests/scripts/`, paths from
`tests/scripts/toolkit_paths.py`.

## Scope

- In: `code/concentration.py` and `tests/scripts/test_concentration.py`.
- Out of the coder's scope: the reviewer rule in `claude/.claude/agents/code-reviewer.md` and the close-branch
  wording that reads the new line. The lane edits those prompt files directly, with a rule-meter run.

## Phase Status

- [ ] Phase 1: concentration.py prints the docs, tests and code split and flags an oversized part (risk: low)

## Phase 1: concentration.py prints the docs, tests and code split and flags an oversized part

`concentration.py <base-sha>` prints a second line after the gate line:

`Diff split: docs <n> (<p>%), tests <n> (<p>%), code <n> (<p>%) of <total> added lines.`

- The split reads the same committed `git diff --numstat -z --no-renames <base>...HEAD` as the gate.
- A file is in tests when `source_paths.is_test_path` holds. Otherwise it is in docs when `source_paths.is_doc_path`
  holds. Every other file is in code. Lockfiles and generated files (`source_paths.is_uncounted_path`) and binary
  files count nowhere.
- Shares are rounded to whole percents. With no added lines, every share is 0%.
- When the total is at least `BRANCH_TRIGGER_LINES` and the docs or the tests part is over `SPLIT_SHARE_LIMIT`
  (a new constant, 40%), the line ends with
  `OVERSIZED: <part> <p>% (limit 40%): check each new <part> file against a plan step, criterion or finding, and cut the rest.`
  It names each part that passes, docs first. Otherwise the line ends with `No part over 40%.`
- The script's docstring describes the second line.

**File**: `claude/.claude/scripts/code/concentration.py`
**Test**: `tests/scripts/test_concentration.py`

#### Automated Verification

- `python3 tests/parallel_tests.py test_concentration.py` passes.
- `bash tests/lint.sh claude/.claude/scripts/code/concentration.py tests/scripts/test_concentration.py` passes.

## Plan Deviations

- The queue item's "flags any part over a set share" flags the docs and tests parts only: the code part is the work
  the ticket asks for. Ruled by the diff-growth lane (criteria owner `session`), 2026-11-25.
