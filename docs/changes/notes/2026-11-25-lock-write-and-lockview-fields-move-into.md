---
type: "Change"
change_type: "changed"
title: "Lock write and LockView fields move into calibration_lock"
description: "`calibration_lock.py` now owns the lock write as well as the read: `mutation_lock.py` calls `write_lock` instead of building the fields itself, `LockView` carries `raw_file`, `pre_hash` and `run_id`, and `positive_int` lives in `script_utils`."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-25T14:22:49-06:00"}
seq: 2
kind: "fix"
components: ["script/mutation-lock", "script/calibration-lock", "script/script-utils"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_mutation_lock.py::MutationLockTest::test_lock_writes_the_fields_the_guard_reads_and_a_byte_identical_backup"
asked: ""
proof: []
unmeasured: ""
---

## Change

`calibration_lock.write_lock` writes the lock in one atomic step with the same fields `mutation_lock.lock_fields` wrote; `mutation_lock.py` calls it and drops its `json` import. `LockView` gains `raw_file`, `pre_hash` and `run_id`, read with the module's defaults, so `read_lock_view` stays the one place that builds a view and `OwnLock` no longer re-reads the raw lock. `positive_int` moves to `script_utils` for any argparse caller. The docstrings of `calibration_lock_path`, `legacy_lock_path` and `backups_folder` name the folders they read.

## Evidence

The branch-exit review's smell reviewer found the lock format written in two modules and the view fields read twice. The toolkit rule names `lib/calibration_lock.py` the one owner of the lock format.

## Result

`tests/scripts/test_mutation_lock.py::test_lock_writes_the_fields_the_guard_reads_and_a_byte_identical_backup` pins the key set and every value the guard reads; `tests/scripts/test_calibration_lock.py::LockIsLiveTest` pins the timeout boundary exactly at and one second past the limit; `tests/scripts/test_script_utils.py::PositiveIntTest` covers zero, negative, float, text and empty input. 281 tests in the five touched files, 0 failed.

## Watch

None: no behavior changed. A `check`, `lock` or `restore` run whose output differs from the pre-change text is the regression to look for.

## Back-out

Move `write_lock` back into `mutation_lock.py` as `lock_fields` plus a `write_text_atomically` call, drop the three `LockView` fields and read them in `OwnLock` again, and put `positive_int` back into `mutation_lock.py`.
