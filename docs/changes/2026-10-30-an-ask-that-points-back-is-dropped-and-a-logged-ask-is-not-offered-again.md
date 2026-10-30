---
type: "Change"
change_type: "fixed"
title: "an ask that only points back to another ask is dropped, and a logged ask is not offered again from another repo"
description: "The review-loop script drops a pointer-back ask before the packet is written, and review_fix.py packet reads the session's asks-logged row before it offers asks."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T12:00:00-05:00"}
seq: 390
kind: "fix"
components: ["script/review-loop", "script/review-fix", "script/handback"]
evidence: ["session-report"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_an_ask_that_only_points_back_to_another_ask_is_dropped"
asked: ""
proof: []
unmeasured: "No intake row counts pointer-back asks or asks offered again after asks-done; the stored packets on this machine hold none of the reported shape."
---

## Change

`review_loop_findings.pointer_ask_split` takes out each ask whose text names another ask (`the open ask ...`, `the earlier ask ...`, `ask 2`), asks no question (no `?`) and carries no `change:` marker, when another ask is there to point to: a real ask in the same review or an open ask from an earlier round. `LoopRun.split_review` applies it before the review is recorded, so the pointer ask files no finding row and asks-done needs no outcome word for it. A pointer ask with nothing to point to stays.

The packet carries each pointer ask in its ask list as `{"text", "file_line", "drop_reason"}` with no question, so `handback.drop_unaskable_asks` drops it and `print_dropped_asks` shows one `DROPPED ASKS` line: `ask only points back to another ask, so it was dropped: '<text>'`. A real ask the rule misreads stays visible.

`review_fix.py asks-done` appends an `asks-logged` row (packet_id, repo) to the session's hand-back store once every outcome is logged. `review_fix.py packet` reads it after the per-repo stage check: a packet whose asks this session already logged prints `ACTION: done` naming the repo that logged them, and offers and logs nothing. Before, a `packet` rerun from a different repo than the one asks-done ran in found no review-fix state there and offered the logged asks again.

## Evidence

A `/code` question listed three asks; ask 3 read "The open ask about pinning the window still stands." with that same sentence as its change, so asks-done demanded an outcome word for it. Separately, `packet` was rerun from the main checkout after asks-done ran in a sibling worktree, and it offered the logged ask again with a `--packet` flag.

## Result

Over the 333 asks in this machine's 543 parseable stored packets (234 old free-text packets do not parse), the rule drops none: the one ask that names `ask 1` asks a question. Two tests fail without the change: a review with two asks, a pointer ask and a question that names `ask 1` yields three packet asks, three ask rows and one dropped-ask warning, and a `packet` rerun from another repo after asks-done prints `ACTION: done` with the logging repo and writes no ledger row.

## Watch

None: no intake number counts either shape.

## Back-out

Remove `pointer_ask_split`, `points_back_to_an_ask` and `ASK_POINTER` and their call in `split_review`, the `pointer_asks` outcome key and `POINTER_ASK_REASON` in `review_loop_packet.py`, and the `drop_reason` branch of `handback.dropped_ask_warning`; remove `record_asks_logged`, `repo_that_logged_the_asks`, `ASKS_LOGGED_ROW` and their calls in `review_fix.py`; revert the two tests.
