---
type: "Change"
change_type: "changed"
title: "hillclimb finds process, agent and cut candidates, not only script fixes"
description: "The hillclimb skill lists four more kinds of moment (a stage that changed nothing, a step in the wrong owner, a model or context mismatch, a stop for a ruling), four matching fix rows, and a closing check that asks for a non-script candidate and at least one cut."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T10:57:37-06:00"}
seq: 1
kind: "user-rule"
components: ["skill/hillclimb"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-27: the user asked that hillclimb find process, agent, skill and cut waste in work sessions, not only script fixes, and that it land on master"
proof: []
unmeasured: "One run per arm and level (3 on, 3 off) is below the runs an open task needs; the fixture's process waste is loud enough that the skill without the lines already queued process candidates in 3 of 3 off runs by the detector's keyword reading. Only the Python orders-session stack was run. No intake number reads a mix of fix kinds; the peer-reported count (16 of 23 hillclimb queue items touch a script) is the baseline to re-read after the next batch of hillclimb items."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`claude/.claude/skills/hillclimb/SKILL.md`: four moment kinds under "Find the moments", one sentence that a cost repeated over many turns is one moment listing every turn, four rows in the fix table (stage that changed nothing, step in the wrong owner, model or context mismatch, stop for the user or a ruling), and a closing paragraph: when every candidate is a script or a check, read the session again for the last four kinds; the report names at least one cut or says what was searched and that none showed.

## Evidence

Judgment: hillclimb reports listed mostly script and check fixes (16 of 23 queued hillclimb items touched a script, per the peer's count), while sessions also lose time to idle loop ticks, a lane that ran every stage for a change with no effect, the main session doing a lane's merge, suite and push, and stops for rulings the session could make.

## Result

Rule meter, scenario HC06, one run per cell, live, opus, Python orders-session fixture (20 idle loop ticks, a no-effect prompt-line lane, hand-run merge/suite/push, a stop for a ruling, one pull error naming no file). The on arm is the live skill; the off arm cuts the four fragments above.

| level | on | off |
|---|---|---|
| supportive | COMPLIED | VIOLATED |
| neutral | COMPLIED | COMPLIED |
| competing | COMPLIED | COMPLIED |

Totals: on 3/3, off 2/3 (+33 points). Read the off arms: all three found process candidates unprompted (the loop polling, the hand-run lane merge, the stop for a ruling); the one off VIOLATED came from no named cut, not from missing process candidates. The on arms named all four new kinds with the table's row names. The fixture is too loud to separate the arms at this run count; the effect is unproven. Stacks run: Python orders session only. Not run: TypeScript session, a session with no process waste (does the check invent cuts), more runs per arm.

## Watch

None: no intake number reads fix kinds.

## Back-out

`git checkout claude/.claude/skills/hillclimb/SKILL.md` removes all added lines.
