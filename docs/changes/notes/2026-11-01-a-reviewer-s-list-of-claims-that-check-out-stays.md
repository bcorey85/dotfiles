---
type: "Change"
change_type: "fixed"
title: "A reviewer's list of claims that check out stays out of the asks"
description: "A review whose finding is followed by a lead-in such as \"The other claims check out:\" and a list of confirmations now gives one ask, not one ask per confirmation, so the user answers only real decisions (one real ask had become four)."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T04:56:48-06:00"}
seq: 443
kind: "fix"
components: ["script/review-fix", "script/review-loop"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_an_ask_followed_by_a_list_of_claims_that_check_out_parses_as_one_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The review loop's finding parser (`review_loop_findings.item_start_lines`) treats a line at the item indent that ends in a colon, after an item, as the lead-in of the reviewer's notes. The bullets under it continue the item before it instead of each starting a finding, until a bullet that opens with a file:line, which still starts its own finding.

## Evidence

- A code-reviewer ask ended with "The other claims check out:" and three confirming bullets; the packet showed four asks, each confirmation with its own proposed change, and the user answered all four. The same shape appears in reviewer replies from at least two other sessions on this machine.

## Result

- The two new parser tests fail before the change and pass after.
- Over 1,112 reviewer replies on this machine, 3 parse differently: two lists of confirmations or notes now fold into one ask (6 → 1 and 4 → 1 asks), and one trailing "checks found no other problems" list drops from 6 nits to 2; the one left over opens with a file:line, so it still counts. No other reply changes.

## Watch

None: no intake number counts asks per finding.

## Back-out

Revert the commit.
