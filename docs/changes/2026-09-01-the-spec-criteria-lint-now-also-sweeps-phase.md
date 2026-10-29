---
type: "Change"
change_type: "changed"
title: "The spec criteria lint now also sweeps phase bodies and change lists for test paths"
description: "The spec criteria lint now also sweeps phase bodies and change lists for test paths, files and directories both, not only file-target lines."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 9
kind: "behavior"
components: ["agent/spec-criteria", "script/spec-criteria-lint"]
evidence: ["census"]
watches: []
---

## Change

The spec criteria lint now also sweeps phase bodies and change lists for test paths, files and directories both, not only file-target lines

## Evidence

census

### Anchor reasons

Anchor `agents/spec-criteria.md`, section `## Damage-path sweep — before you finish` (evidence: unproven):

Walk the failure surface, not the happy path: every input the change reads, and every destructive or preview/apply operation on a stale view. Where the ticket is silent, ask rather than default or invent. This is the block that produces the open questions the caller walks with the user, and it has never been exercised against a seeded silent ticket.

Anchor `agents/spec-criteria.md`, section `## The file` (evidence: unproven):

The criteria file template and the prose-out-of-the-shipped-tree rule with its pointer to the vocabulary file. The analogous one-sentence vocabulary rule beat a file pointer in two other agents, where no run followed the pointer; that result was not measured here.

## Result

Its glob list mirrored the ownership hook correctly but it read one line type, so a phase step assigning a test edit in prose — "update the tripwire in this test", "sweep the files under this test directory" — went past it and the coder hit the deny mid-phase. Three separate specs collided this way. Verification sections stay exempt: naming a test file in the command that runs it is correct. Report-only, like the lint's other path check, because a phase body may legitimately mention a test the test-writer owns. Verified on a fixture plan: fires on both the file and the directory form, silent inside both verification sections and on file-target lines, clean plan still exits clean.

## Watch

—

## Back-out

—
