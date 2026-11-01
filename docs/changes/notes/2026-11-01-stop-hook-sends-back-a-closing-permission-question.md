---
type: "Change"
change_type: "added"
title: "Stop hook sends back a closing permission question"
description: "The Stop hook now sends a main-session turn back once when it ends on a permission question for a reversible step, including \"do you want that ...?\" forms. On the bench this cut ask-ended turns from 7 of 8 to 0 of 8 and fixed the reported bug in 5 of 8 runs against 0 of 8, with no unasked commit, push or deploy. The hook's median time is 47 ms against a 12 ms bare Python start."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:02:33-06:00"}
seq: 420
kind: "structured"
components: ["script/staged-claim-gate"]
evidence: ["bench", "tests"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py"
asked: ""
proof: ["2026-11-01-a-stop-hook-that-sends-back-a-closing-permission"]
unmeasured: "No intake metric reads ask-ended turns yet; lane B adds the watch id and replaces this line."
---

## Change

`staged_claim_gate.py`, already wired on Stop and SubagentStop, gains a second check from the new
`gates/permission_question.py`. On the Stop event only, and only when `stop_hook_active` is false, it blocks a message
whose last 400 characters end on a permission question to go on: `want me to`, `do you want that|this|it|them|those|these
...?`, `shall I`, `should I`, `would you like me to`, `okay to proceed`, `go ahead and`, `ready to`. The reason tells the
session to take the step itself and to ask only before a step that cannot be undone or leaves the machine.

A question that names an outward or lasting step (commit, push, merge, deploy, publish, release, delete, drop, reset,
rebase, force, send, email, post, install, upgrade, migrate) passes. So do choice questions ("Do you want the short or
the long report?"), questions that sit before a long tail, and subagent hand-backs. A message that trips both checks gets
one block with both reasons. No settings.json edit.

The classifier is the bench rig's (`~/dev/evals/askstop2/rig/permission_stop.py`), widened with the `do you want
that ...?` form the bench missed in 2 of 8 treated runs.

## Evidence

Finding `2026-11-01-a-stop-hook-that-sends-back-a-closing-permission`: 8 runs per arm, Claude Code 2.1.316, dotfiles
edebc93c. Ask-ended turns fell from 7 of 8 (Wilson [0.53, 0.98]) to 0 of 8 ([0.00, 0.32]). The reported bug was fixed in
5 of 8 runs against 0 of 8, with no unasked commit, push or deploy. Opus cache read rose about 40% (119k → 166k mean).

Hook time, 30 runs each with a permission-question payload, median: bare Python start on an empty file 12.2 ms, master's
gate 57.4 ms, this branch's gate 47.3 ms. The new check adds no time past run-to-run spread; the hook costs about 35 ms
over a bare start.

## Result

`test_staged_claim_gate.py` passes 43 of 43, with five new tests that failed before the change. Ruff is clean on the
touched files.

## Watch

Lane B adds the watch id.

## Back-out

Revert the commit. That removes `permission_question.py`, the Stop-only branch in `staged_claim_gate.py` and the
`PermissionQuestionTest` tests together.
