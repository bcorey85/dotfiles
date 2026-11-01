---
type: "Change"
change_type: "fixed"
title: "A no-review exemption belongs to the loop that asked for it"
description: "A review loop's hand-back is exempt from the reviewer check only when its own dispatch prompt asks for no-review, so a clean loop that ran no reviewer can no longer take the exemption of a no-review loop that failed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:58:02-06:00"}
seq: 434
kind: "fix"
components: ["script/handback"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::NoReviewExemptionOwnerTest::test_a_clean_loop_with_no_reviewer_cannot_take_a_failed_no_review_loop_s_exemption"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; no intake number counts exemptions claimed by the wrong loop."
---

## Change

`handback_hook.claim_no_review` takes the loop's transcript. When the transcript holds the dispatch prompt, the loop is exempt only when that prompt names no-review mode (`loop_transcript.NO_REVIEW_MODE`), and the claim records a `no-review-exempt` row for that agent. With no prompt it keeps the old count of no-review dispatches against exemptions. `handle_hook` reads the transcript once and passes it to both claims and to `transcript_gates`; an unreadable transcript skips the transcript gates and says so on stderr (fail-open, as before).

## Evidence

judgment: a bug hunt showed a no-review loop that handed back a blocker without claiming its exemption, then a normal loop that ran no reviewer and handed back clean. The second loop matched the spare no-review dispatch row, which carries no agent id, and passed.

## Result

The normal loop's clean hand-back is denied with "clean but no reviewer ran"; a no-review loop's own clean hand-back still passes.

## Watch

—

## Back-out

Revert the commit.
