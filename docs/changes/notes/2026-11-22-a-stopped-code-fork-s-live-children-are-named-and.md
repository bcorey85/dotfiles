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

Verify-branch fixes: the loop is stopped only when its pid file was written between the code-fork's first review start and its last record (else `not_this_run`); a /review or /fix fork's loop reads `not_code_phase`, since only a /code review loop is stopped; a failed `ps` reads `query_failed`; `stopped` is reported only after every process of the loop's process group exited within two seconds, else `signalled` (`process_group.wait_until_group_gone`, on the group id read before the signal); an OSError from the signal exits non-zero with a named error line; the deny text and the skill sentence tell the session to TaskStop each agent id and to rerun the command for a launch with no agent id yet. `agent_interrupted` is unchanged: of 119 real subagent transcripts holding the interrupt text, 43 end on the interrupt record and read as interrupted; the other 76 hold the text only inside tool results or tool calls, or after the interrupt the agent went on (one transcript, 77 more records), so a trailing tool_result, attachment or assistant record means the agent resumed. Three real ending shapes are fixtures in tests/scripts/fixtures (`interrupt_*_transcript.jsonl`). No TaskStop hook event has been captured on this machine; the hook test input follows the PreToolUse schema.

The loop stop is `stop_fork_loop` in fork_children.py; `review_launch.py` owns a different `stop_loop`, so the names stay apart.

## Evidence

work incident. The 2026-11-22 cancel was the main session running TaskStop on the code-fork directly. TaskStop returned success and named no children. The coder kept running and rewrote a deleted file.

## Result

Median of 30 runs each: the hook on a pass fixture 134.8 ms, the hook on a deny fixture 132.7 ms, `python3 -c pass` 16.0 ms.

## Watch

The settings.json wiring is pending at agent-evals-c3. Until it lands the hook never fires and the command is the only route. No opencode port of code-fork.md or the /code SKILL.md exists: `rg -n "fork_children|code-fork" opencode/` finds nothing.

## Back-out

Delete `fork_children.py` and the added sentence of the skill's description.
