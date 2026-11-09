---
type: "Change"
change_type: "fixed"
title: "a code phase review holds the files dirty before the run"
description: "A /code phase review holds every file that was dirty before the run started and still holds the same bytes: the file stays out of the review scope and the findings, and fix coders are told never to edit it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-09T09:13:29-06:00"}
seq: 3
kind: "fix"
components: ["skill/code", "script/code-review-start", "script/review-loop-script"]
evidence: ["code-runs-hold-the-files-another-session-left"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest::test_a_file_dirty_at_the_phase_start_with_the_same_bytes_is_held_out_of_the_review"
asked: ""
proof: []
unmeasured: "The SKILL.md step 3 line is a script-call step (run phase_start.py and keep the printed sha), not a behavior rule; the tests pin the behavior."
---

## Change

- `code/phase_start.py` (new): writes `<git dir>/code-phase/start.json` with HEAD and a sha256 of each dirty file, and prints HEAD as the phase base. The record is kept across a run at the same HEAD, so files that earlier phases of the run left dirty stay the run's own. `--new-run`, or a moved HEAD, replaces it.
- `code_review_start.py` holds each recorded file that is still dirty with the same bytes: it drops the file from the handoff `files` list and the phase's changed files, and passes it to the loop as a `held files:` prompt key. A record of another base stops the review start. No record holds nothing and says so on stderr.
- `review_loop_held.run_held_files` merges the caller's `held files:` with the files a `files:` line leaves out, so the loop's existing held-file handling covers `/code`.
- `/code` step 3 runs `phase_start.py --new-run` for the first phase of a fresh run and `phase_start.py` otherwise. The handoff block says the `/code` files list leaves out the held files.

## Evidence

Queue item `code-runs-hold-the-files-another-session-left`: two of the three incidents behind the `files:`-line fix were `/code` runs, which pass no `files:` line and so held nothing.

## Result

The new `phase_start` tests fail without the change (the script does not exist), and the loop test `test_a_held_files_line_with_no_files_line_keeps_that_file_out_of_the_review_and_the_fix` fails on a loop that ignores the `held files:` key. Both pass with the change. Suite: `bash tests/run.sh` passes, 3315 tests, 0 failed.

## Watch

None. A held file that changes during a coder call still shows as a `Tool fault:` line in the hand-back.

## Back-out

Revert the commit.
