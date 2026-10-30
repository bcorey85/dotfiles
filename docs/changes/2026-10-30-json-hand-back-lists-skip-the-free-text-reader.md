---
type: "Change"
change_type: "fixed"
title: "JSON hand-back lists skip the free-text reader"
description: "Every ask in a JSON hand-back reaches the user as its own question with its own outcome row, and an open class routes the scoped rerun, because typed lists stop being turned back into text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T01:47:39-05:00"}
seq: 314
kind: "fix"
components: ["script/handback", "script/review-fix", "script/review-loop-script", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::JsonPacketTest::test_a_json_packet_with_n_asks_some_without_file_line_yields_n_asks"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `handback.read_json_entries` reads each JSON list entry of `fixed`, `skipped_fp`, `findings_remaining` and `ask` as a
  mapping checked against its required text field. A bare string or an entry with no text field is a packet problem
  that names the key and position (`ask[1] must be a JSON object, not a string`). `fold_bullets_into_asks` and the
  bare-string path no longer run on a JSON packet. An ask with no `file_line` is `unlocated` and stays its own ask.
- The packet carries `open_classes`, a list of strings. `review_fix.scoped_rerun_lines` reads it; the `OPEN_CLASS`,
  `NEGATED_CLASS` and `RECEIPT_CLAUSE` regexes are deleted. `review_loop_script` fills it with the class members the
  repair pass left unfixed, and `review_loop_packet` sends it.
- `script_utils.json_string_list` and `is_string_list` are the one JSON-list-of-strings reader; the coder's open
  questions line and the packet's `open_classes` both use them.
- The review-loop agent's return template lists `open_classes` and says the entries of `fixed`, `skipped_fp`, `findings_remaining` and `ask` are objects.

## Evidence

Read of `handback.py`: a JSON ask without `file_line` matched `continues_lead_ask` and folded into the ask before it,
so one answer decided two asks and one outcome row was logged. A bare-string ask took `entry_from_text` and skipped
the `file_line` and change checks. `NEGATED_CLASS` counted "was" as a negation, so "the class was not closed" read
as closed and the cap-reached route skipped the scoped rerun.

## Result

A JSON packet with N asks, some without `file_line`, yields N asks and N outcome rows. The new tests fail before the
edit: the unlocated asks fold away and the packet holds fewer than N asks. Targeted tests and ruff pass. The free-text
fallback for non-JSON hand-backs is unchanged.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. A reviewer packet that carries no `open_classes` key reads as no open class, so a revert needs no
data change.
