---
type: "Change"
change_type: "removed"
title: "hand-back packets are JSON only: the free-text fallback parser is gone"
description: "handback.parse reads only one JSON object; the old free-text key: value grammar, its stderr note and its grammar-only tests are deleted."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T09:04:21-05:00"}
seq: 317
kind: "fix"
components: ["script/handback", "script/loop-transcript", "script/script-utils"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::JsonPacketTest::test_a_message_that_is_not_one_json_object_is_a_packet_error"
asked: ""
proof: []
unmeasured: "The fallback's stderr note was the only signal of an old-form packet; no intake row counts free-text hand-backs."
---

## Change

`handback.parse` reads one JSON object and nothing else. A message that does not open with `{` raises a PacketError: "the packet must be one JSON object, and the message does not open with `{`". The free-text parser (`parse_free_text`, the flow-mapping and inline-pair readers, `read_list`, the item-key table and their regexes) and its "parsed an old free-text packet" stderr note are deleted. The readers that fold string entries of a JSON list into asks stay: a JSON `ask` list may still hold plain strings. The helpers only the free-text parser used (`unquote`, `unquoted_mask`, `top_level_braces`, `quote_opens_at` and `QUOTE_OPENERS` in `script_utils.py`) are deleted with their tests in `test_script_utils.py`.

`loop_transcript.PLAN_IMPACT` now matches only the `"status"` key of a JSON packet; the free-text `status: plan-impact` line no longer counts.

The tests that fed free-text packets now build JSON packets: `test_handback.py`, `test_review_fix_script.py`, the `test_code_step*.py` files, `test_fixes.py`, `test_review_loop_gate.py`, `test_review_loop_script.py` and `test_script_utils.py`. Tests that only checked the free-text grammar, or compared the free-text form with the JSON form, are deleted. The ask and blocker tests run on the JSON form.

The opencode `review-loop.md` port still shows the free-text packet. It was not moved to the JSON form when Claude's prompt was, and opencode runs no hand-back hook, so this change leaves it.

## Evidence

Queue item delete-the-free-text-hand-back-packet-fallback: the fallback was kept for one release so a session running an old review-loop prompt was not stranded. The live review-loop prompt hands back one JSON object.

## Result

`test_a_message_that_is_not_one_json_object_is_a_packet_error` (free text, prose and empty input) fails against the previous `handback.py`, which parsed the free-text form. The affected 12 test files run 1952 tests, all passing (555 skipped, 2 expected failures).

## Watch

None: with the stderr note gone, an old-form packet now shows as a `stop-parse-failure` from `review_fix.py packet`.

## Back-out

Revert the commit. The free-text grammar and its tests come back together.
