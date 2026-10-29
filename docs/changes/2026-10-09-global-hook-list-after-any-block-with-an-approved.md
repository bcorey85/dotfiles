---
type: "Change"
change_type: "changed"
title: "Global hook list: after any block with an approved path (Write or Edit, a script file, the direct command"
description: "Global hook list: after any block with an approved path (Write or Edit, a script file, the direct command, the call without the blocked fragment), the agent retries once, lists the block, and keeps working."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["rule/global-claude-md"]
evidence: ["hook block log", "judgment"]
watches: []
---

## Change

Global hook list: after any block with an approved path (Write or Edit, a script file, the direct command, the call without the blocked fragment), the agent retries once, lists the block, and keeps working; it still stops when no approved path exists and always after a blocked credential or `.env` read

## Evidence

hook block log, judgment

### Anchor reasons

Anchor `CLAUDE.md`, section `## Safety Rails` (evidence: hook block log, removal round, sealed round, judgment):

Lists the commands the hooks block. By judgment: never unstage files that the user staged. After a block the agent redoes the step once through its approved path (Write or Edit, a script file, the direct command, the call without the blocked fragment), lists every block in its report, and keeps working. It stops when no approved path exists, such as a git write or a destructive delete, and always after a blocked credential or `.env` read. No disguised retry, no skip comment without the user's say-so. The retry clause covers all blocks because work hook block logs for Oct 3–8 show most blocks were not shell writes: inline interpreters 16 a day, credential reads 11.5 a day (about a third false alarms), `sh -c` 6 a day, pipe-to-shell 4 a day. Those rows carry no repo field, so dotfiles and agent-evals sessions are not filtered out. Unproven on outcomes: watch stops right after a block in the review queue. Without the list the coder hit blocks it could have avoided and lost a diagnosis. The gate names, the omp contract note and the workflow-gate escapes were cut. Loads in every main session and subagent. The list no longer names coder writes to test files. The coder now writes the tests for the behavior it implements, and the test-file hook binds no agent type. In a sealed round of 72 valid runs on ticket-level cells, the new flow had 0.25 hidden failures per run, against 0.42. The old flow sent a test writer after the coder. The gap is inside two standard errors. The new flow was about 20% faster and used about two-thirds more Opus cache read per run. The Write-or-Edit clause is by judgment: in one bench ticket run, 9 of 15 coder dispatches hit the shell write gate, 8 redid the write with Edit and kept going, and 1 stopped and ended its phase with no review. Work logs cannot size it, because the shell write gate does not log its blocks. The block is now about 150 words.

## Result

Work hook block logs, Oct 3–8, unfiltered (rows carry no repo field): inline interpreters 16 a day, credential reads 11.5 a day with about a third false alarms, `sh -c` 6 a day, pipe-to-shell 4 a day. The old text let the agent continue only after a blocked shell write, so every other block ended the turn. About 50 more words in every session. Effect on work: watch turns and subagent runs that end right after a block in the review queue.

## Watch

—

## Back-out

restore the Safety Rails text from git
