# Decisions

- Cut: the code-review-loop item's second Done-when line (a brief turns off a named gate; the loop records it as skipped and returns its packet). It needs `review_loop_script.py` and `review_fix.py`, which this lane must not touch. It stays on the queue item review-loop-full-check-ignores-a-caller-s-no-local. Ruling by agent-evals-c3-owner at 2026-11-25 (option B).
- The `lane-status` allow rule lives in `settings.json`, which a lane never edits. The lane sends the proposed line to agent-evals-c3-owner.
