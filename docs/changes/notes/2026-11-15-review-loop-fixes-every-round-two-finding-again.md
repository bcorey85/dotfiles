---
type: "Change"
change_type: "removed"
title: "Review loop fixes every round-two finding again"
description: "The review loop sends every round-two `fix` finding to the fix coder again, whatever its class and wherever its line sits. The rule that left a non-bug fix outside the previous fix diff open in `findings_remaining` is removed from `review_loop_script.py` and `review_loop_fix_induced.py`."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T11:14:16-06:00"}
seq: 3
kind: "user-rule"
components: ["script/review-loop", "script/review-loop-fix-induced"]
evidence: ["user rule", "round-two-review-deferral-leaves-fix-findings-open"]
watches: []
test: "tests/scripts/test_review_loop_round_two_fixes.py::RoundTwoFixesTest::test_a_round_two_docs_fix_outside_the_fix_diff_reaches_the_coder"
asked: "2026-11-15: asked by the user"
proof: []
reverts: "2026-11-09-review-loop-defers-a-round-two-fix-outside-the-fix"
unmeasured: "The change removes a rule; the queue item holds the counts that led to it, and no run measures the loop after it."
---

## Change

- `review/review_loop_script.py`: `LoopRun.defer_outside_fixes` and its call in `walk` are gone. Every round's `fix` findings go to the fix coder. `walk` no longer turns a converged run into `deferred` for a finding this rule held; `findings_remaining` holds only what the coder left.
- `review/review_loop_fix_induced.py`: `split_outside_fixes`, `is_outside_fix`, `FIXED_OUTSIDE_FIX_DIFF` and `previous_fix_diff` are gone. `fix_induced_tag`, `previous_fix_ranges` and `ranges_of_path` stay: they write the telemetry tag that says whether a finding sits inside the previous fix diff.
- The `deferred` status stays. `capped_review.effective_status` still returns it for a capped packet, and `/code` still prints `### Deferred to branch exit` for that case, so no skill, agent or command text changes.
- This reverses `2026-11-09-review-loop-defers-a-round-two-fix-outside-the-fix.md`.

## Evidence

User rule, 2026-11-15: the user asked to back it out. The queue item `round-two-review-deferral-leaves-fix-findings-open` holds the reading behind it: a work-log count of later-round fix findings left open after the deferral, with no branch-exit step that reads them, and a read of the open findings in this machine's loop packets.

## Result

`tests/scripts/test_review_loop_round_two_fixes.py` adds 7 tests; 6 fail against the base script. They cover a round-two docs, smell and bug finding reaching the coder brief, a finding with no file:line, a finding with no class, a round of only outside-diff findings ending at the round cap, and a resumed loop over a fix diff the deferring version left on disk. Seven tests that pinned the deferral are removed, and one (the tail-path case) is rewritten as a `fix_induced_tag` test.

## Watch

Cost: about one more coder call per loop run, and at most 22% more Sonnet cache read per run. The two watches on the deferral, `review-loop-round-two-defers-outside-fix-diff` and `review-loop-defers-non-bug-later-round-findings`, are to be closed on this ruling by the session that owns the queue item.

## Back-out

Restore `split_outside_fixes` and its helpers in `review_loop_fix_induced.py` and `LoopRun.defer_outside_fixes` with its `walk` call in `review_loop_script.py`, from commit `9c1218e6`.
