---
type: "Change"
change_type: "fixed"
title: "An accepted ask with no location must name the file to change"
description: "asks-done refuses an accepted or modified ruling on an unlocated finding ask whose change names no file, and asks for a modified ruling that names it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 23
kind: "fix"
components: ["script/review-asks", "script/review-fix-asks"]
evidence: ["accepted-design-decision-ask-reaches-the-coder-as"]
watches: []
test: "tests/scripts/test_review_asks.py::RefuseUnlocatedChangesTest::test_accepted_with_no_location_and_no_file_in_the_change_is_refused"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_asks.refuse_unlocated_changes` runs at both asks-done call sites. It exits 2, logs nothing, and asks for `modified:<the change, naming the file and the edit>`.

## Evidence

An accepted design-decision ask with no location reached the fix coder as a bare proposed change with no file and no subject.

## Result

RefuseUnlocatedChangesTest in `test_review_asks.py`.

## Watch

None.

## Back-out

Revert the commit.
