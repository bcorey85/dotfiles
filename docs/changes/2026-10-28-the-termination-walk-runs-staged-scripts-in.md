---
type: "Change"
change_type: "changed"
title: "The termination walk runs staged scripts in-process"
description: "The termination walk ran `coder_gate.py` and `coder_packet.py` as python3 processes on most nodes; it now runs them in-process, and its no-row-yet wait is ten times shorter, so the file runs in about half the time with the same visited nodes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:59:31-05:00"}
seq: 181
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_termination.py::TerminationTest::test_a_staged_script_run_in_process_gives_what_its_process_gives"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The walk patches `run_command` in code_step, code_step_start and code_step_review. A `python3 <staged script>`
  command runs through `runpy` in the verb's repo and returns the exit code and output a process gives. Every other
  command runs as before.
- The no-row-yet presets wait 0.02s with a 0.01s poll, not 0.2s with 0.05s. The walk runs each verb in-process, so no
  row lands during the wait.

## Evidence

- test_code_step_termination.py hit the 1200s per-file cap in the full suite, in the script-loop walk, at load 6.
- A 400-node profile of the main walk: `coder_gate.py clear` processes took 14.4s of 39.2s, the no-row-yet sleeps 6.5s.
  In the script-loop walk, `coder_gate.py set`, `coder_gate.py clear` and `coder_packet.py` took 9.2s of 40.3s.
- 400-node walks, masked visited-node dumps: the same nodes before and after, in both walks. Main walk 35s to 68s
  before, 13s to 20s after; script-loop walk 37s before, 19s after, at load 13 to 20.

## Result

- Both walks visit the same nodes in about half the time.
- The whole file, alone through tests/parallel_tests.py: 391.6s at load 14, against 771.7s at load 18 before.

## Watch

—

## Back-out

Revert the commit.
