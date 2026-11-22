---
type: "Change"
change_type: "changed"
title: "Stop hook tells the session to take the step it offers and list it"
description: "When a main-session turn ends asking permission for a step that can be undone, the Stop hook now tells the session to take the step and end its report with a Decisions taken list, where it used to say to drop the question and not start the step."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T10:30:00-06:00"}
seq: 4
kind: "structured"
components: ["script/staged-claim-gate"]
evidence: ["replacement bench", "census", "tests"]
watches: ["stop-hook-take-the-step"]
test: "tests/scripts/test_staged_claim_gate.py"
asked: "asked by the user"
proof: ["2026-11-22-a-stop-hook-reason-that-says-take-the-step-you"]
unmeasured: "A step the user would have refused: the bench's offered step is one the user wants. Unasked work that replaces an answer to the user's question: the pass for a reply to a user's question is unchanged and the bench does not exercise it. Sonnet main sessions: the bench ran Opus only."
overlap: "closing-permission-stop-hook (closed 2026-11-07) read the share of turn ends closing on a permission question; this edit changes only the reason text, so that share is not expected to move. stop-hook-take-the-step reads a different count, the bare go-ahead after a report with no question."
---

## Change

`gates/permission_question.py`: the `REASON` string the Stop hook sends back. Old: send the message again without
the closing question, and do not start the step it offers unless the user's request already covers it. New: take the
step you offer now, then end the report with a "Decisions taken" list, one line for each step taken without asking,
with the reason. The last sentence is unchanged: ask only before a step that cannot be undone, leaves this machine,
or a rule requires the user's yes for. The classifier, the pass for a reply to a user's question and the pass for
an outward step are untouched, and the hook still blocks a turn once.

## Evidence

census: after the 2026-11-07 wording, turn ends closing on a permission question fell, but about half of the bare
go-ahead replies at work still followed one, and the stop itself stayed: the session dropped the question and ended
the turn with the step undone.

replacement bench: 8 runs per arm on a billing web app whose task leaves a second, unreported copy of the bug. The
arms differ only in this string.

## Result

Offered step finished: 0 of 8 → 8 of 8. Commit, push or deploy taken unasked: 0 → 0. A "Decisions taken" list that
names the step: 8 of 8. Opus cache read in the blocked turn: mean 175.3k → 247.0k (up 41%), output 2201 → 2970,
wall 30 s → 42 s; the extra is the step itself, which the old reason left for a later turn after a human reply.
An earlier wording that made acting depend on the step being inside the user's task finished it in 0 of 8.

Stack: one Python web app, Opus main session. `bash tests/run.sh` passes.

## Watch

`stop-hook-take-the-step`: the share of typed-reply turn ends with no question and a reply that only says go on,
expected down. WORSE or NO CHANGE: restore the old string or say here why it stays.

## Back-out

Restore the old `REASON` string in `gates/permission_question.py` and the two assertions in
`tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest`.
