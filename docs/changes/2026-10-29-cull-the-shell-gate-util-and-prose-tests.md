---
type: "Change"
change_type: "removed"
title: "Cull the shell, gate, util and prose tests"
description: "Deleted tests whose bug another test already catches, merged near-duplicates into tables, and sped up sleeps; no script behavior changed."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T08:16:45-05:00"}
seq: 244
kind: "fix"
components: []
evidence: ["census"]
watches: []
test: "tests/run.sh::full suite, 0 failed"
asked: ""
proof: []
unmeasured: ""
---

## Change

Tests only; no script changed. Every deletion was checked against a named test that still pins the same behavior. No fails-before test exists because no behavior changed; kind fix is kept for the ledger.

Cuts made:
- test_format_changed: dead fixtures and two tests deleted; marker tests are a 5-row table; resume and skip-switch tests merged; the npx test uses a git-only PATH dir.
- test_telemetry_switch: 5 tests deleted, 5 merged into 2.
- test_script_utils: 2 busy-ledger tests and a redundant assertion deleted; 7 table tests parameterized; RunProcess timeouts shortened.
- test_coder_gate: 2 tests deleted, clear-timeout test merged, make-scope tests one table.
- test_rg_path_gate: deny and allow cases are two tables; the settings test is replaced by an rg_path_gate row in test_hook_if_filters.
- test_quality_check_cap: 9 tests deleted, 5 merged into others, the shared module loader removed, and the sleep now runs only after a post-tool event.
- test_git_discipline_gate: stash-message and empty-stdin tests removed or merged; cd tracking and direct-edit exemptions are two tables over shared repos.
- test_full_check: failure-summary, setup-fault, full-suite-line and base-run tests merged into tables; the exit-zero failure and pass summary tables moved to FullCheckTest, which uses a plain temp dir.
- test_shell_write_gate and test_wait_loop_gate: 6 tests deleted (heredoc lexer cases pinned by test_shell_statements, the HINT text, the operator table); skip-comment and for-loop tests merged.
- test_comment_bloat_gate: 3 lexer-edge tests deleted (pinned by test_source_text); param-id and dash tests merged.
- test_stale_prose: state-key test replaced by one that moves a shown hit to another line; saved-state and output-cap tests merged.
- test_test_run_output, test_check_output, test_branch_base: mocha/bun, cargo filter, runs_tests, no-tests, origin/local main/master and detached-head tests merged into tables; the limit=None test merged into the chained-summary test.

Cuts skipped: other candidate merges in test_test_run_output whose inputs take different code branches.

## Evidence

Census of test names against the tests that pin the same behavior. Full suite before: 3938 tests in 98 files, wall-clock 242.4s, sum of per-file seconds 1450.9s, 0 failed. After: 3775 tests in 98 files, wall-clock 230.3s, sum of per-file seconds 1210.7s, 0 failed. Merged cases still run as table rows. (counts adjusted by hand for the one test added after the full-suite run; seconds are from that run) After merging the integration branch, which carries another test cull: 3693 tests in 99 files, wall-clock 232.6s, sum of per-file seconds 1173.4s, 0 failed.

## Result

163 fewer test functions, 240s less summed test time, no failures.

## Watch

None; tests only.

## Back-out

Revert the test files in this change.
