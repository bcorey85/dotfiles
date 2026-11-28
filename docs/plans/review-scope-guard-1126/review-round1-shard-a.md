# Plan review round 1 (shard a, unsharded)

VERDICT: NEEDS CHANGES (1 blocker, 5 gap)

## BLOCKER
- Phase 1 §2 `undo_ac_quote_pass` and `test_loop_puts_back_the_ac_quoted_line_and_keeps_the_fix`: `put_back_lines(..., whole_stretch=False)` with no `may_replace` puts the lost line in place of the most similar stretch line. Exercised: `restore_protected_lines("limit = 1\nlimit = 2\nlimit = 3\nlimit = 4\nlimit = 5\n", "limit = 1\nlimit = 20\nlimit = three\nlimit = 4\nlimit = 6\n", [3], False)` → `'limit = 1\nlimit = 3\nlimit = three\nlimit = 4\nlimit = 6\n'` ("limit = 20" ratio ~0.84 beats "limit = three" ~0.73). The pass's line-2 fix is lost and the reworded line stays, failing AC4/AC5. The comment guard uses a `may_replace` predicate (review_loop_comment_removal.py:208-210).

## GAP
1. Phase 2 §1: `record_pass_writes` runs just before `return CoderResult(...)`, so a pass whose undo failed (review_loop_coder.py:142-147, `failed_call_error(..., died=False)`) never records outside writes; `failed_pass_blocker` finds nothing; AC8 fails on that path. Record right after `claude_call_reply` returns.
2. Phase 0 §3 / Phase 1 §2: test_review_loop_coder.py:627 moved to `PassSnapshots` with no `ac_quotes` value; copying Phase 0's `None` gives an AttributeError in Phase 1's `undo_ac_quote_pass(None, ...)`.
3. Phase 3 Agent-run sweep cannot fail: `RealPlansTest` (test_plan_format.py:1060-1100) calls only `manual_verification` and `parse_plan`; no phase adds `plan_ac_quotes` to it.
4. Plan § Acceptance Criteria (public boundary, no mocks) vs AC6, AC7 (fake-host unit tests only) and AC9 (`outside_writes` unit test only): by the plan's rule these ACs have no covering test.
5. Phase 1 §2 fault text `{file}`: nothing says how the failing file is known; `plan_ac_quotes` reads two files and lets a bare `PlanFormatError` propagate.

## NIT
- In-process mocks with `CallReply(text, "")` add "could not run" notes to module-global `OUTSIDE_WRITE_FAULTS`, leaking across tests.
- Phase 1 §3 loop-level tests: file not named.
- Lint lists: Phase 1 lints review_loop_main.py (unchanged in Phase 1); Phase 2 omits review_loop_calls.py and review_loop_partial_fix.py.
- Phase 3 first criterion is evidence (already green), not a check that can fail; label it.
- Incident AC: unknown whether "Bash timeout up to 600000 ms" was quoted in the source AC; if not, the guard would not have caught it.

## Unverified (outside the tree)
- 394-transcript survey; transcript written by the time `claude -p` exits; out dir under the git dir.

Hook blocks: one Bash call (an `rg` with `-r .` and no path), re-run with explicit paths.
