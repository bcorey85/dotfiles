---
type: "Change"
title: "The code_step test file runs the script in-process"
description: "test_code_step.py runs code_step.main() in the test process instead of starting python3 for each of about 4,000 script calls, and one review wait test stops waiting 15 seconds for a stop row it never writes. The file goes from 339 s to 141 s run alone."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T19:10:36-05:00"}
seq: 209
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_an_asks_coder_state_without_its_accepted_asks_does_not_tick_the_phase"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `run` in test_code_step.py calls the new `run_in_process` on the main thread: it sets argv, stdin, the
  environment and the working folder, points every code-step module's `CLAUDE_DIR`, `SCRIPTS_DIR` and
  `REVIEW_LOOP_SCRIPT` at the test's staged folder, empties the `code_step_core.STATE_DIRS` cache for the call, calls `code_step.main()`, and returns the exit code, stdout and stderr a process would give,
  including exit code 1 and a traceback on a crash.
- A late hand-back from a timer thread, and a run under an older Python, still start a process.
- `test_after_review_waits_for_a_review_loop_row_newer_than_the_review_dispatch` waits 5 seconds, not 20: the test
  writes no stop row, so the reader waited out 15 seconds for one after every hand-back.
- `every_accepted_ask_already_done` in code_step_report.py returns False for a state with no accepted asks, where it
  raised a KeyError and `code_step.py resume` ended with a traceback. The run now stops cleanly with the phase
  unticked.
- `test_an_asks_coder_state_without_its_accepted_asks_does_not_tick_the_phase` now also asserts no traceback on
  stderr.
- The in-process runner and its exit-code helper live in tests/scripts/in_process.py, shared with the termination
  test.

## Evidence

- A coder could not run the file inside the 600 s tool timeout. Per-call timing: about 4,000 script calls spent 356
  of the file's 360 seconds in subprocesses, about 50 ms of each a python3 start and the code-step imports.
- The traceback assertion failed before the code fix (`KeyError: 'acceptedAsks'` on stderr) and passes after.
- New test, comparing exit code, stdout and stderr of a process and an in-process run for status, an unknown verb and
  `start --help`:
  `test_code_step.py::CodeStepTest::test_the_script_run_in_process_gives_what_its_process_gives`.

## Result

- test_code_step.py run alone, plain (the 360 s above is the profiled run, which adds timing overhead): 339 s
  before, 141 s after, 557 tests, all passing. The slowest test went from 17.9 s to
  6.2 s.

## Watch

- None: a test-runtime change, read from the suite's per-file times.

## Back-out

- Revert the commit.
