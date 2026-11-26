---
type: "Change"
change_type: "changed"
title: "verify-branch writes a fetched ticket to the path verify-prep names"
description: "verify-branch's exit-4 row writes the fetched ticket to the path verify-prep's message names, in the git dir, not the tmpfs scratchpad."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T04:41:30-06:00"}
seq: 9
kind: "fix"
components: ["skill/verify-branch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_a_git_dir_plan_folder_resolves_by_ticket_branch_with_no_arguments"
asked: ""
proof: []
unmeasured: "No rule-meter fixture shows where a session writes a fetched ticket; the line swaps a fixed scratchpad path for the path verify-prep prints. Shipped unmeasured on agent-evals-74's ruling (2026-11-26); the user rules before the weekend merge."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`claude/.claude/skills/verify-branch/SKILL.md` exit-4 row: "write its raw fields to `<scratchpad>/<KEY>-ticket.md`" became "write its raw fields to the ticket path the message names". verify-prep's exit-4 message now names `<git dir>/claude-plans/<KEY>/00-ticket.md`.

## Evidence

Queue item `a-lane-plan-and-its-criteria-in-the-tmpfs`: a reboot cleared the scratchpad that held a verify task dir and its criteria. The row named the scratchpad and would have kept a fetched ticket there, contradicting the new message.

## Result

Unmeasured. `bash claude/.claude/scripts/tools/rule-anchors.sh check` passes.

## Watch

None.

## Back-out

Revert this commit alone; verify-prep's message still names the git-dir path.
