---
type: "Change"
change_type: "fixed"
title: "A stopped code-fork's live children are named, and a TaskStop of a code-fork with live children is refused once"
description: "A cancel of a code-fork now names the coders and reviewers still running, so none keeps writing after the stop."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T00:00:00-06:00"}
seq: 22
kind: "fix"
components: ["skill/code", "script/fork-children"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_fork_children.py::ForkChildrenTest.test_taskstop_of_a_fork_with_a_live_coder_is_denied_once"
asked: ""
proof: []
unmeasured: ""
---

## Change

`fork_children.py <code-fork id>` lists the agents a code-fork started that have not finished or been stopped, and stops the repo's detached review loop when it is that code-fork's own. Its `hook` verb refuses a TaskStop of a code-fork with a live child once and names each child. The skill's cancel sentence tells the session to run the command when the code-fork does not stop. fork_children.py reads a child whose transcript ends on an interrupt record as stopped.

## Evidence

work incident. The 2026-11-22 cancel was the main session running TaskStop on the code-fork directly. TaskStop returned success and named no children. The coder kept running and rewrote a deleted file.

## Result

Median of 30 runs each: the hook on a pass fixture 134.8 ms, the hook on a deny fixture 132.7 ms, `python3 -c pass` 16.0 ms.

## Watch

The settings.json wiring is pending at agent-evals-c3. Until it lands the hook never fires and the command is the only route. No opencode port of code-fork.md or the /code SKILL.md exists: `rg -n "fork_children|code-fork" opencode/` finds nothing.

## Back-out

Delete `fork_children.py` and the added sentence of the skill's description.
