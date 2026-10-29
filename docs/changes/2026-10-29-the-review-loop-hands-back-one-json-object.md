---
type: "Change"
title: "The review-loop hands back one JSON object"
description: "The review-loop agent and the scripted review loop hand back one compact JSON object, handback.py parses it with json, and the old free-text form still parses for one release with a stderr note."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T16:49:57-05:00"}
seq: 280
kind: "fix"
change_type: "fixed"
components: ["agent/review-loop", "script/handback", "script/review-loop-script", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::JsonPacketTest::test_a_json_packet_validates_to_the_packet_its_free_text_form_gives"
asked: ""
proof: []
unmeasured: ""
overlap: "The scripted-review-loop-escapes watch is still open on the same review-loop hand-back. This edit changes only the packet's format, not what the loop checks or decides, so read that watch as before and treat a jump in parse failures as this edit's."
---

## Change

- `review-loop.md`: the Return packet section is one JSON template with every packet key, then a rule per key. The
  agent hands back that object alone, compact, with no fence and no prose around it.
- `handback.py`: `parse()` reads a JSON object first (a stray fence or whitespace is removed). A wrong shape raises
  `PacketError`; `validate()` and the packet rules are unchanged. The repair text asks for one JSON object.
- The free-text grammar stays for one release, under one banner comment, so a session already running is not
  stranded. When it parses a packet it prints `handback: parsed an old free-text packet; hand back one JSON object` to
  stderr.
- `review_loop_packet.packet_message` writes the scripted loop's packet as JSON. `loop_transcript.PLAN_IMPACT` also
  matches the JSON status. The review and fix skills name the status as a packet key.
- Done-when clause 2 of the item (delete the free-text grammar) moved, with the driver's sign-off, to the queue item
  `delete-the-free-text-hand-back-packet-fallback`. It starts once the stderr note has gone unseen for a day after
  install.

## Evidence

- The free-text grammar split an ask and lost a blocker, and was patched three times. A JSON object has no grammar of
  its own to get wrong.

## Result

- 48 tests failed before and pass after, including the named test, the ask and blocker cases on the JSON form, and a
  test that the agent's template parses with exactly the packet's keys. Old-form tests pin the fallback.
- Review asked whether an unknown JSON key fails the parse. It goes to the trailer, as the free-text form did, so the
  change adds no check.
- Output tokens per packet on 20 test fixtures (regex BPE estimate): median 56 → 68.5, total 1639 → 1854 (+13%) as
  compact JSON. Indented JSON would be +28%, so the agent is told to write it compact.

## Watch

—

## Back-out

Revert the commit. Packets already handed back as JSON then fail to parse until the loop is re-dispatched.
