---
type: "Change"
change_type: "fixed"
title: "A code-fork cannot hand back while a skill fork it started in the background runs"
description: "The open-child hand-back gate now counts a review, code or fix Skill that a code-fork started as a background forked run, so the fork waits for it instead of handing back with no loop status."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T05:40:19-06:00"}
seq: 8
kind: "fix"
components: ["script/open-child-gate"]
evidence: ["tests", "transcript read"]
watches: []
test: "tests/scripts/test_open_child_gate.py::OpenChildGateTest::test_code_fork_hand_back_while_its_skill_fork_runs_is_denied"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/loop_transcript.py` maps each Skill call whose result says `status: "forked"` and `background: true` to the forked run's `agentId`, and `open_skill_forks()` lists those runs with no task notification, no agent message and no API-error end. `review/open_child_gate.py` `live_children` adds each one whose sibling transcript does not show it finished, so a code-fork hand-back is denied once per child and told to wait with `code_wait.py agent <agentId>`. `fork_children.py` reads `live_children`, so its TaskStop guard and cancel listing name the forked run too. A foreground Skill is never counted.

## Evidence

Transcript read: 43 background forked Skill launches inside code-fork transcripts on this machine; several were followed at once by a SubagentHandback with no loop status. The new test fails on the old scripts and passes on the new ones.

## Result

Not measured.

## Watch

None.

## Back-out

Revert `read_skill_fork`, `open_skill_forks` and the Skill branch of `read_tool_use` in `lib/loop_transcript.py`, the second loop in `open_child_gate.live_children`, and the new tests in `tests/scripts/test_open_child_gate.py`.
