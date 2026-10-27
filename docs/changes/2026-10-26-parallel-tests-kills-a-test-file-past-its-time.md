---
type: "Change"
title: "parallel_tests kills a test file past its time limit"
description: "The suite runner kills a test file's process group after 1200 s (TEST_FILE_TIMEOUT_SECONDS) and reports that file as failed by name, so one hung file no longer stalls tests/run.sh."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:43:01-05:00"}
seq: 75
kind: "fix"
components: ["script/parallel-tests"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_parallel_tests.py::FileTimeoutTest::test_a_file_past_the_limit_is_killed_and_reported_as_failed"
asked: ""
proof: []
unmeasured: "Suite runs are not logged; no intake number reads it."
---

## Change

`run_job` starts each test file in its own process group. Past `FILE_TIMEOUT_SECONDS` (1200, env
`TEST_FILE_TIMEOUT_SECONDS`) it kills the group, appends "`<file>` timed out after Ns and was killed" and marks the file
FAIL. The slowest file, the code-step termination walk, takes about 240 s on Linux.

## Evidence

A full run on macOS had the termination walk file still running at 65 minutes with 0 tests reported; the suite never
finished until the worker was killed by hand.

## Result

A hung file fails by name inside 20 minutes and the rest of the suite reports.

## Watch

None.

## Back-out

Revert the commit.
