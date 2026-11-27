---
type: "Change"
change_type: "changed"
title: "the Stop hook keeps the blocked reply in the user's pane"
description: "When the staged-claim gate blocks a Stop, its output also carries the blocked reply in systemMessage, so the user still sees the reply the hook sent back."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-27T11:10:45-06:00"}
seq: 1
kind: "user-rule"
components: ["script/staged-claim-gate", "script/stop-block"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::StopBlockOutputTest::test_a_stop_block_carries_the_whole_reply_in_the_system_message"
asked: "2026-11-27: asked by the user that a Stop hook never hide a reply from them"
proof: []
unmeasured: "Hook code, not prompt text, so no rule-meter run; no intake field counts replies that a Stop block hid from the user."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `lib/stop_block.py` `block_line` builds a Stop hook's block output. `staged_claim_gate.py` prints it in place of its own JSON. For a Stop block the output adds `systemMessage`: a label line, a blank line, then the blocked reply, cut at 10,000 characters with a cut line. A SubagentStop block and an empty reply carry no `systemMessage`.

## Evidence

Judgment, from the hooks docs (https://code.claude.com/docs/en/hooks#json-output: `systemMessage` is a warning shown to the user, capped at 10,000 characters per field; #stop-decision-control for `decision` and `reason`). Before the change a blocked Stop replaced the reply in the user's pane with the hook's reason alone. The gate tests now pin the whole reply in `systemMessage`, the 10,000-character cut, and no `systemMessage` on a SubagentStop block.

## Result

Median hook time over 21 runs (`time_hook.py` on `payload_block.json`): before (be9a5807d) bare Python start 7.7 ms, `staged_claim_gate.py` 43.6 ms; after, bare Python start 7.8 ms, `staged_claim_gate.py` 44.0 ms (measured at 313801c5b; later edits to `announced_step.py` were not re-timed).

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
