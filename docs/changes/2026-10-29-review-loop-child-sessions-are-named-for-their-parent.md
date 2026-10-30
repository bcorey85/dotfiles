---
type: "Change"
change_type: "fixed"
title: "The review loop script's child sessions are named as children of the session that ran it"
description: "Each `claude -p` step of review_loop_script.py starts with `--name \"child of <parent> (<role>)\"`, and orchestration.md says such a peer is a step of that run, not a rival worker."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T23:40:00-05:00"}
seq: 296
kind: "fix"
components: ["script/review-loop-script", "rule/orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_each_child_session_is_named_as_a_child_of_the_session_that_ran_the_loop"
asked: ""
proof: []
unmeasured: "Whether a worker that sees a `child of` peer still stops to ask who owns its ticket."
---

## Change

- `review_loop_script.py`: every model step runs `claude -p ... --name "child of <parent> (<role>)"`. The parent is
  the ListAgents name of the session that ran the loop, read from its `~/.claude/sessions/<pid>.json` entry by
  `script_utils.session_display_name`. When no entry holds that session id, the label is `session <id>`.
- `orchestration.md`: a ListAgents peer named `child of <name>` is a headless step of that session's run, not a rival
  worker: never message it, and go on with your work.

## Evidence

- A worker saw a busy peer named with its own repo-and-ticket prefix and no herdr pane, took it for a second worker,
  and stopped to ask the orchestrator who owned the ticket. The peer was gone a few minutes later.
- A live `claude -p --agent coder` step of review_loop_script.py registered as an interactive peer named
  `agent-ledger-led-81-2c`, after its cwd, the same scheme as the worker's own name. Its parent process was
  review_loop_script.py.
- A headless `claude -p --name "probe child of e6"` registered under that name, with `nameSource: "user"`.

## Result

- The two naming tests fail before the change (no `--name`) and pass after. The guidance test fails before the
  orchestration line and passes after.

## Watch

—

## Back-out

Revert the commit.
