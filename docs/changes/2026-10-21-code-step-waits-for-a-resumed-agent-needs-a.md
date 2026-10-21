---
type: "Change"
title: "code-step waits for a resumed agent, needs a dispatch time, and skips gated phases"
description: "code-step waits for the hand-back of the coder or review loop of this phase, including one resumed by SendMessage. It stops when a state has no dispatch time, instead of reading an earlier row. start skips an open phase whose status line has a gate clause, and names it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T12:11:31-05:00"}
seq: 15
components: ["script/code-step", "script/plan-format", "skill/plan-format"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- **Wait for this phase's agent:** after-coder, after-plan-edit and after-review read only rows that came after this phase's dispatch. A PLAN-IMPACT scan reads only the rows of a coder whose gate passed. If a state in a hand-back stage has no dispatch time, code-step stops and says to run `start --phase N` again. The fallback to the run's start time is gone.
- **Resumed agents:** when a coder or review loop is resumed by SendMessage, code-step waits for it. The wait cap counts from the first wait, which code-step saves once. The handback hook puts a resumed review loop back in the review stage and writes its row, the same as a resumed coder. While the resumed agent has not handed back, the stop says to run the same verb again, not `start`.
- **Stopped report:** a coder that stopped on "no reviewable change" keeps its report. After the resume, the PLAN-IMPACT scan still reads it.
- **Finished plan:** a stop on a plan with all phases done names `start --task "<text>"`.
- **Gate clause:** a Phase Status line can carry `gate: <text>`. When `start` picks the phase itself, it skips each open phase with a gate and names the phase and its gate. `start --phase N` still runs a gated phase. If every open phase has a gate, `start` stops and opens no dispatch. code-step does not judge the gate condition. `plan_format.py` parses the clause. `skills/_shared/plan-format.md` tells the planner how to write it.

## Evidence

Work incidents: in two work slices, after-coder and after-plan-edit returned a result while an async coder still ran. One returned `ask-user` on a report that did not exist yet. In one slice, a review loop resumed after the wait cap did not register, so after-review said that no review was pending. In the same slice, `start` picked an open phase whose slice gate had not passed, and its open dispatch blocked the hand-back of the next agent. On a finished plan, `start` did not say that it needed `--task`.

A code review of the staged change found that a resumed coder hit the wait cap at once, that a resumed review loop had no cap, and that a stopped coder's PLAN-IMPACT was lost after the resume. All three were fixed before install. A second review found that the auto-advance text named a gated phase, that the gate clause matched plain title words, and three smaller faults in the resume path. Those were fixed too, and the gate clause now needs a dash in front.

## Result

Staged 2026-10-21 in the third script fix batch. 331 code-step and plan-format tests pass. The state-machine walk explored 564,470 paths with 0 failures. Against the installed scripts, 21 of the new tests fail and 5 error. Installed 2026-10-21. The full suite passed: 1,461 tests in 39 files.

## Watch

None. No intake metric counts stale hand-backs or phases started past a gate.

## Back-out

Restore the previous `code-step.py`, `plan_format.py`, their tests and `skills/_shared/plan-format.md` from the dotfiles history.
