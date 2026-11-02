---
type: "Change"
change_type: "fixed"
title: "a /code fork cannot hand back while its coder still runs"
description: "A /code fork that tries to hand back while a coder it dispatched still runs is told to stay active and wait with code_wait.py, so the work no longer sits with no owner."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T10:09:14-06:00"}
seq: 6
kind: "fix"
components: ["script/open-child-gate", "script/code-wait", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_open_child_gate.py::OpenChildGateTest::test_code_fork_hand_back_while_its_coder_runs_is_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/open_child_gate.py` (PreToolUse on SubagentHandback) now gates `code-fork` as well as
`goal-blind-researcher`. A fork's hand-back is denied while a background launch in its transcript has no report and
the child's own transcript (`agent-<id>.jsonl` beside the fork's) does not show it finished: no `finished` in its
meta file, no delivered hand-back, no API-error end. The deny names the live agent ids and tells the fork to stay
active and run `code_wait.py agent <agentId>` with the Bash timeout set to 600000. Each child denies once (kept in the
handback store), so a child that never ends cannot trap the fork. `agent_finished` moved from `code_wait.py` to
`lib/loop_transcript.py`, so the gate and the wait read one finished test. The researcher path is unchanged.

The 120 s wait cap is not a toolkit limit. `code_wait.py` waits at most 540 s and the skill says to run it with the
Bash timeout set to 600000; a 120 s cap is Bash's default timeout, which a call that leaves out `timeout` gets. The
deny text repeats the 600000 timeout.

## Evidence

The handback-send-enforce message is the harness's own prompt when a subagent ends a turn without a hand-back; the
toolkit cannot change it. Replaying local code-fork transcripts at each SubagentHandback attempt found 11 attempts made
while a child launch was open and the child's transcript went on for 16 s to 25 min after the attempt. The code-step
script's hand-back gate denied those; it was removed with the move to plain /code steps, and nothing gated a fork
since.

## Result

Before: a fork that ended its turn while its coder ran was told to hand back and did, and the run sat with no owner.
After: its first hand-back per live child is denied with the wait command.

## Watch

None. Check by hand: a /code fork transcript that shows an `open_child_denied` deny followed by a `code_wait.py agent`
call, and no fork hand-back that names an unfinished coder.

## Back-out

Revert the commit; the gate then passes every code-fork hand-back again.
