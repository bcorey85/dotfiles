---
type: "Change"
change_type: "fixed"
title: "a blocked Stop asks the session to repeat the hidden reply"
description: "A main-session Stop block's reason now tells the session the user did not see the blocked reply, and the announced-step reason names the line it flagged, so the next reply quotes it and repeats the text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T18:40:00-06:00"}
seq: 1
kind: "user-rule"
components: ["script/staged-claim-gate", "script/stop-block"]
evidence: ["work incident", "tests"]
watches: []
test: "tests/scripts/test_stop_block.py::BlockLineTest::test_a_shown_reply_ends_the_reason_with_the_hidden_reply_note"
asked: "2026-11-27: the user reported never seeing the blocked reply and asked for it fixed"
proof: []
unmeasured: "Hook code, not prompt text, so no rule-meter run. Whether the next reply follows the note is unmeasured until the next live block."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/stop_block.py` `block_line` adds `HIDDEN_REPLY_NOTE` to the reason of every Stop block that shows the reply. The note tells the session the user did not see the blocked reply, and asks it to open its next message with the flagged line, quoted, then the whole reply again, corrected. `staged_claim_gate.py` adds `Flagged line: "<sentence>"` to the announced-step reason. The `systemMessage` stays.

## Evidence

Live, 2026-11-27: the gate blocked a main-session Stop for an announced step. Fed the same reply by hand, the gate printed `systemMessage` with the reply. The user's pane showed "Stop hook reported a problem" and the reason only. Public reports describe the same gap: https://claudeissues.com/issue/50542-stop-hook-systemmessage-json-not-rendered-as-visible-line-in-v2-1-114-plugin-sco and https://claudeissues.com/issue/35707-systemmessage-from-stop-hooks-not-displayed-in-remote-mode. The session's next reply is the one channel that always reaches the pane.

## Watch

None: tests pin the reason text.

## Back-out

`git revert` the commit.
