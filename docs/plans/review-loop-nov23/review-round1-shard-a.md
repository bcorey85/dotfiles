# Plan review round 1, shard a

Verdict: NEEDS CHANGES (0 blockers, 10 gaps, 5 nits). Reviewer: plan-reviewer, 2026-11-24.
The gaps map to G5-G14 in 03-decisions.md, in this order.

## Gaps
1. Phase 4/6: the new keys never reach the written packet (`review_loop_packet.packet_message` :60-97) or the header that is read (`handback.read_header` :325-360). → G5
2. Phase 4: the default for an old packet is stated two ways (0 vs None). → G6
3. Phase 4: the plan never says whether `fix_rounds` counts across a relaunch (`review_loop_main.py:157`). → G7
4. Phase 4: the test never asserts the scoped re-review that AC6 names. → G8
5. Phase 5: the new line format breaks 14 pinned asserts in 4 test files outside the phase's verification, and `_shared/review-fork-run.md:13` is not updated. → G9
6. Phase 2/3: `_shared/review-fork-run.md:37` still says to hold every user-only ask. → G10
7. Phase 3: no test proves a capped packet stays not clean after a ruling, and the resume's apply step exists only in skill text. → G11
8. Phase 6: the plan names the wrong exception (`ReplyShapeError`, not `ModelCallError`), and the outcome tags have no source. → G12
9. Phase 6: the backup covers `files_in_scope` only, so the put-back can miss files that `pass_scope` lets the pass write. → G13
10. Phase 2: the plan never says who computes the new `rule_instruction` flag. → G14

## Nits (fixed in spec.md by the lane)
- Phase 3: AC2 maps to test (b). Test (a) passes on master.
- Phase 5: one test file, test_code_wait.py. Its fails-on-master claim rests on the round label.
- Phase 4: drop the crash_outcome copy from progress (dead code).
- Phase 4: add an `— atomic:` reason (packet keys, writer and reader change together).
- Phase 7: fork_write_scope adds `S/code` to sys.path. The fixture is built from the hook-input fields that fork_write_scope already reads in its tests.
