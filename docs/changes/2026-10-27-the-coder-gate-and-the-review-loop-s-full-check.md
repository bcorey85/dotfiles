---
type: "Change"
title: "The coder gate and the review loop's full check run the repo's own test command"
description: "The hand-back gate runs the plan phase's listed test commands verbatim instead of a bare pytest, vitest or jest it builds itself; a run that found no test or no package manifest is a setup fault, not a code failure; the full check stops as setup-fault with no coder repair; failure text keeps the failing test's name; a round-two prompt goes on stdin."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T21:03:12-05:00"}
seq: 137
kind: "fix"
components: ["script/code-step", "script/coder-gate", "script/review-loop-script", "script/handback", "script/review-fix", "agent/review-loop", "skill/coder-core"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_listed_django_test_command_is_the_gates_test_command_and_no_pytest_runs"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_gates.py` reads a phase's Automated Verification commands through one function (`listed_commands`).
  When the phase lists a test command (`lib/test_run_output.py:runs_tests`: `pytest`, `vitest`, `jest`, `mocha`,
  or a `test` / `test:*` / `test-*` word given to a script runner or Django's `manage.py`), the listed command runs
  verbatim and replaces the derived test commands of its own runner family only: JS (`npx vitest run`, `npx jest`,
  `npm test --`), Python (`<runner> pytest`) or cargo (`cargo test`). A listed command whose family the text does not
  show (`make test-unit`, `just test`) replaces all of them. Derived typecheck, lint and clippy commands stay. A listed
  command whose scan scope `coder_gate set` would refuse is not taken. No JS test is derived for a package when the
  phase names no script file in it.
- The command scope scan moved from `coder_gate.py` to new `lib/check_scope.py`, on the shared shell splitter. It
  peels runner wrappers (`pipenv run`, `env`, `timeout`) before judging, reads `python3.12` and `./manage.py`, and
  skips the values of `manage.py test` options.
- New `lib/check_output.py` holds the setup-fault classifier, moved out of `coder_gate.py`, and both the gate and
  the full check use it. A run that found no test (pytest exit 5, "No test files found", "No tests found",
  "NO TESTS RAN", with no failing test) and a missing package manifest (pnpm `ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND`,
  npm `ENOENT` on `package.json`, yarn) are setup faults. A collection error such as `ImproperlyConfigured` still
  denies.
- `review_loop_script.py`: a full check that fails with a setup fault gets no coder repair and stops with the new
  status `setup-fault`. Its blocker names the command and its output tail. The routing text in `review_fix.py` and
  `code_step_review.py` says it is an environment or toolkit fault, not a code failure. `handback.py`,
  `review_fix.py`, `code_step_review.py`, both `review-loop.md` copies route it to the user like `critical-blocker`.
  In the full check a missing module from outside the repo stays a code failure (it may be a dependency the diff
  added and did not declare) and gets one coder repair; only the coder gate treats it as a setup fault. The check
  finder prefixes a subfolder package's step with
  `(cd <folder> && ...)` and leaves out JS steps when the repo has no `package.json`.
- The full-check tail and the gate's denial put the failing-test lines (pytest `FAILED`/`ERROR`, unittest
  `FAIL:`/`ERROR:`, vitest/jest `FAIL` and `×`; deduplicated, at most 20) above the output tail.
- `claude_call` sends the prompt on stdin. A round-two prompt that holds a large fix diff passed the 128 KB limit of
  one argument and crashed the loop with `E2BIG`.
- `coder-core` tells the coder to run its tests through the phase's listed command, else the repo's documented
  runner, and plain `pytest` only when the repo names none. A collection error or a run with no tests is not a pass.

## Evidence

- Eight work sessions on one day hit the gate's own test command. A Django repo had `pipenv run pytest` fail at
  collection with "settings are not configured", and the coder spent all three denials on passing code. A vitest
  package whose tests run only through a make target got "No test files found" every time. A full check that ran
  pnpm at the root of a repo whose `package.json` is in a subfolder stopped the loop as `critical-blocker`. A failed
  full check's 40-line tail cut off the failing test's name.
- The review loop on this change crashed in round two with `OSError: [Errno 7] Argument list too long`.
- One test per shape, each failing before the change: the listed Django command, a listed `cd backend && ...`
  command, the listed make target, a missing pytest under `pipenv run`, a collection error that denies, an empty
  vitest run that never denies, a Django `FAIL:` line 200 lines above the end of a full check, the pnpm
  no-manifest setup fault (first check and after the coder repair), and a round-two prompt over 128 KB.

## Result

- Full suite after the merge with master: 3371 tests in 93 files, 0 failed; ruff and the duplicate check clean.
- The review loop converged. Its open questions were decided: the scan code moved to `lib/check_scope.py`; a
  missing outside module stays a code failure in the full check; Playwright and unittest were not added to the
  test-command rule, since no session listed either; a listed test command replaces only its own runner's derived
  tests; Django `-k`/`--tag` option handling and moving `runs_tests` were left as they are.
- Master's `full_check.py` now carries the setup-fault reading and the failing-test lines, so the scripted loop and
  the agent loop both print `setup fault (exit N)` and stop with `status: setup-fault`.

## Watch

—

## Back-out

Revert the commit.
