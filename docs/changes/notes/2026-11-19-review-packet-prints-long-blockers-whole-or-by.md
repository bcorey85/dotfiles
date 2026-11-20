---
type: "Change"
change_type: "fixed"
title: "review packet prints long blockers whole or by file path"
description: "The review packet prints each blocker whole up to 2000 characters; a longer blocker is written to a file under the review-fix folder and the packet prints its path."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:12-06:00"}
seq: 9
kind: "fix"
components: ["script/review-fix"]
evidence: ["review-packet-truncates-blocker-text"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_blocker_past_2000_characters_prints_a_path_to_a_file_holding_all_of_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

The new `review/review_blocker_text.py` owns the blocker print limit. `review_fix.py` `blocker_lines` prints a blocker
whole up to the limit and, past it, writes the full text under `review_fix_dir()/blocker-text/` and prints the path.

## Evidence

The packet cut blocker text short, so the caller lost the reproduction.

## Result

Two blocker tests in `test_review_fix_script.py` (1200 and 5000 characters).

## Watch

None.

## Back-out

Revert the commit.
