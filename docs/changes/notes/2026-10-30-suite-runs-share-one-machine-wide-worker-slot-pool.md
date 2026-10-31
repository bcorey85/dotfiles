---
type: "Change"
change_type: "fixed"
title: "Suite runs share one machine-wide worker slot pool and run niced"
description: "tests/parallel_tests.py takes a flock slot (nproc slots in a shared folder) before each test file starts and starts its workers at niceness +10, so two concurrent suite runs never run more than nproc test files together and interactive work stays responsive."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T02:39:09-05:00"}
seq: 315
kind: "fix"
components: ["script/parallel-tests"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_parallel_tests.py::SlotPoolTest::test_two_runners_sharing_one_slot_never_overlap_test_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

Each test file (or shard) takes a non-blocking `fcntl.flock` on one of `SUITE_SLOT_COUNT` lock files (default nproc) in
`SUITE_SLOT_DIR` before its process starts, retries every 50 ms while all are taken, and releases it when the file
ends. The default folder is `$XDG_RUNTIME_DIR/dotfiles-suite-slots`, else a per-user folder in the temp dir. The
kernel frees a flock when its process exits, so a crashed run leaks no slot. Each worker process calls `os.nice(10)`
first, and every process its tests start inherits that. Output and exit codes are unchanged.

## Evidence

Two sessions ran the suite at once on a 4-core laptop; each sized its pool from `os.cpu_count()`, load reached 20 to
29 for over ten minutes and another repo's timing tests failed.

## Result

Two runners sharing one slot never run two test files at the same time (test below; a runner without the pool lets
both run at once). A worker's niceness is its runner's plus 10, capped at 19.

## Watch

None: the effect is machine load, which no intake number reads.

## Back-out

Revert tests/parallel_tests.py to size its pool from `os.cpu_count()` and drop the `os.nice` call, and run `run_job_in_slot` directly, dropping `acquire_slot`, `slot_folder` and
`slot_count`.
