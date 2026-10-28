---
type: "Change"
title: "The full check reports its runner summary and its own file changes, and calls a version mismatch a setup fault"
description: "full_check.py quotes the test runner's own summary line and calls an exit 0 with none `unverified`; it names tracked files its command rewrote and files it created, so neither counts as coder work or lands in /code's commit; a package-manager version mismatch is a setup fault; the review loop calls its logger by full path and never writes rows to a file of its own."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T00:18:28-05:00"}
seq: 161
kind: "fix"
components: ["script/full-check", "script/review-loop-script", "script/handback", "script/code-step", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckSideEffectsTest::test_a_tracked_file_the_check_rewrote_and_a_file_it_created_are_named_and_left_in_place"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `lib/test_run_output.py:runner_summaries` reads the runner's own summary lines (pytest, unittest and Django,
  vitest, jest, mocha, cargo, bun, playwright, node --test, go; at most 5). `full_check.py` prints them on a `summary:` line, or
  `summary: not found`. An exit 0 with no summary is `unverified (exit 0, no runner summary)`, not `passed`: no
  finding, no repair, and never called a pass. An exit 0 whose summary reports failures is
  `failed (exit 0, summary reports failures)` and gets the repair a failure gets.
- New `lib/worktree_snapshot.py` records the work tree before the check. After it, even on a timeout, a tracked file
  the check rewrote and an untracked file it created are named and left in place: an edit made in the same work tree
  while the check ran is never reverted. `full_check.py` prints `changed by the check:` and `created by the check:`
  lines.
- The scripted loop's packet carries `full_check_command`, `full_check_summary`, `check_changed` and
  `check_created`, merged across rechecks; `handback.py` reads and renders them. Neither list reaches
  `files_touched`. /code leaves both out of its suggested commit and names them with a restore or delete hint. A
  file that held coder edits before the check rewrote it goes on its own `rewrote edited files:` line and in
  `check_rewrote_edited`: it stays in `files_touched` and in the commit, with a warning and no restore hint.
- `check_output.is_setup_fault`: pnpm `ERR_PNPM_BAD_PM_VERSION` / `ERR_PNPM_UNSUPPORTED_ENGINE`, npm `EBADENGINE`,
  corepack "This project is configured to use" and yarn's node-engine mismatch are setup faults.
- `full_check.py` refuses a `--log` name holding `...`, `<` or `>`.
- `review-loop.md`: any test count comes from the `summary:` line; a run is called the full suite only when it ran the
  CLAUDE.md quality-check command; the logger is called by its full path, and a failed call is a `nit`, never a
  fallback file.

## Evidence

- A loop packet called a 496-test run the full suite of a repo with about 4000 tests; the count came from an
  unrelated printed line, and the log name held a literal `...`. The same packet said the ledger CLI was not on PATH
  and wrote rows to a fallback file.
- Two runs had a full check rebuild a tracked generated file on a backend-only phase (one about 700 lines). The loop
  listed it in `files_touched` and /code put it in its suggested commit. One also stopped as `critical-blocker` on a
  local package-manager version mismatch.
- One test per shape, each failing before the change.

## Result

- Full suite after the merge with the integration branch: 3553 tests in 94 files, 0 failed; ruff and the duplicate
  check clean.
- The review loop converged. Its open questions were decided: the check leaves the files it rewrote or created in
  place rather than reverting them, since an edit made in the same work tree during the check must survive; a
  rewritten file that held coder edits stays in the commit; an exit 0 whose summary counts failures is a failure; the
  four work-tree snapshot implementations stay separate for now.
- Merged with the pinned-Python, environment-gap and no-check-found changes. `run()` reads, in order: passed (or
  unverified, or failed with exit 0), environment gap, setup fault, failed. A pinned-Python check with no runner
  summary now reads `unverified`.

## Watch

—

## Back-out

Revert the commit.
