---
type: "Change"
change_type: "fixed"
title: "The review loop test file runs as four processes, each under the per-process limit"
description: "tests/parallel_tests.py runs test_review_loop_script.py as four processes that each take every fourth test, so a busy machine no longer kills the file at the 1,200 s limit and reports a passing branch as failed."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T13:07:34-06:00"}
seq: 5
kind: "fix"
components: ["script/parallel-tests"]
evidence: ["test-review-loop-script-py-runs-within-10-percent"]
watches: []
test: "tests/scripts/test_parallel_tests.py::ShardedFileTest::test_the_review_loop_test_file_runs_in_several_processes_and_each_test_runs_once"
asked: ""
proof: []
unmeasured: ""
---

## Change

`tests/parallel_tests.py` has a `SHARDS` table: a file listed there runs as N processes, and each process takes the
tests whose position mod N is its index. The table was empty. It now holds `test_review_loop_script.py: 4`. The
1,200 s limit applies to each process. The file's printed seconds are the sum over its four processes.

Each test process now writes how many tests its file holds and how many it took, to a JSON file the runner names in
`PARALLEL_TESTS_SHARD_REPORT`. After every run, for every file, the runner checks the counts (`count_problems`). A
file fails when a process wrote no readable count, when its processes loaded different numbers of tests, when the
tests they ran do not add up to the number the file holds, when a process ran fewer tests than it took, or when one
of several processes ran no test. A crash or a kill at
the limit failed the file before and still does; the kill line now names the process ("process 3 of 4").

The comment on the limit said the slowest process takes about 240 s. That number came from a file that no longer
exists, so the clause is gone.

The test file itself is not split. A split of the 5,202-line file gives the same time margin, but it renames 338
tests, breaks the import in `tests/scripts/test_review_loop_round_two_fixes.py`, and conflicts with five unmerged
branches that edit the file. The shard entry keeps every test name and the count by construction.

## Evidence

On 2026-11-15 the file ran 1,095 s of its 1,200 s limit at load 30, and was killed at the limit twice at load 48 to
57, with 199 tests passed and none failed before the kill.

Measured in one process at load 5 to 11: 338 tests in 186.4 s, a mean of 0.55 s a test. Each test builds a fresh git
repo and starts the loop script as a subprocess. The slowest tests:

- `test_the_fix_coder_prompt_stays_small_with_a_huge_finding_set_and_held_file_list`: 23.2 s
- `test_main_mode_hands_each_round_to_the_main_session_and_reads_its_reports`: 4.63 s
- `test_a_finding_open_after_round_two_dispatches_no_third_round`: 4.63 s
- `test_a_stale_prose_hit_report_over_the_tail_limit_reaches_the_coder_whole_in_its_issues_file`: 2.70 s
- `test_a_plan_impact_ask_reads_the_same_with_a_line_range_or_a_list_of_ranges`: 2.67 s
- `test_a_reviewer_model_line_names_the_model_on_each_main_session_request`: 2.51 s

- `test_a_rerun_of_the_review_logs_the_same_finding_under_the_same_id`: 1.51 s
- `test_a_skip_in_round_one_and_a_fix_in_round_two_are_each_logged_with_their_outcome`: 1.45 s
- `test_a_held_finding_the_next_round_re_reports_and_the_coder_fixes_leaves_the_open_list`: 1.31 s
- `test_a_stale_prose_hit_whose_claims_hold_converges_with_no_unreviewed_fix`: 1.28 s
- `test_a_ruled_plan_fix_raised_again_after_a_rejection_logs_no_finding_row_and_is_not_counted`: 1.28 s
- `test_a_plan_change_ask_is_a_plan_impact_bare_tagged_or_opening_with_its_file_line`: 1.27 s
- `test_a_tail_path_of_a_file_the_coder_created_and_a_held_file_reaches_the_coder_in_a_later_round`: 1.22 s
- `test_a_still_open_class_packet_carries_the_members_left_alone`: 1.19 s
- `test_a_scoped_test_that_cannot_run_names_the_log_that_keeps_its_output`: 1.17 s
- `test_an_ask_the_session_rejected_comes_back_as_a_dropped_ask_not_a_stop`: 1.16 s
- `test_a_finding_skipped_beside_an_impact_that_is_not_held_is_a_plain_skip_not_an_open_fix`: 1.15 s
- `test_an_ask_with_the_title_of_an_earlier_fix_is_its_own_row_and_ask`: 1.13 s
- `test_a_round_two_fix_diff_over_one_argument_limit_reaches_the_reviewer_whole`: 1.12 s
- `test_a_reworded_ask_in_round_two_keeps_one_row_and_one_ask_id`: 1.11 s

The file holds 338 tests, not the 339 the queue item's brief gave. A search for `def test_` matches 339 lines; one
of them, line 1425, is a string a test writes into a fixture file (`def test_case_{number}(): pass`), not a test.
unittest loads and runs 338.

A profile of the 23.2 s test puts 20.1 s in `log_finding`, which starts
one process per finding for 200 findings. That cost is in the loop script, not the test, and is not changed here.

## Result

The four processes run 85, 85, 84 and 84 tests: 338 in all, as before. With two copies of all four processes at
once (eight processes, load 8 to 9), three rounds gave a slowest process of 59.4 s, 58.6 s and 60.8 s. Through the
runner at load 11 the file printed 178.0 s as the sum, and a three-file run took 58.6 s of wall-clock time.

One process took 186 s quiet and 1,095 s at load 30, a factor of 5.9. At the same factor the slowest of the four
processes takes about 360 s, under a third of the limit.

The new test fails on the old runner with "4 != 1 : the file did not run as four processes". A second test holds a
file with no entry to one process. Nine more tests in `tests/scripts/test_parallel_tests.py` cover the checks: a
run that names only the sharded file runs all of it in four processes; a process that crashes fails the file; a
process past the limit fails the file and is named; a process that takes no test fails the file; processes that
load different numbers of tests fail the file; and four tests of `count_problems` and the report reader. Run
against master's runner, nine of the fourteen tests in the file fail.

A run of `python3 tests/parallel_tests.py test_review_loop_script.py` with one other file printed 338 tests, OK.

The file has no `setUpClass`, `setUpModule` or module-level state that tests change. Each of the four processes was
also run alone with its tests in reverse order: 85, 85, 84 and 84 tests, no failure and no error.

## Watch

None. No intake number reads a suite timeout.

## Back-out

Set `SHARDS` back to `{}`. The file then runs in one process again.
