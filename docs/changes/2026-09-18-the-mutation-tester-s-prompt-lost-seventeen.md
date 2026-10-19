---
type: "Change"
title: "The mutation tester's prompt lost seventeen sentences and clauses that explained why a rule exists (1,169"
description: "The mutation tester's prompt lost seventeen sentences and clauses that explained why a rule exists (1,169 words, was 1,418): the authorized-agent framing, the invented-mutation, global-lock, red-baseline, diff-hash, and SessionStart-guard reasons, the reasons behind the verdict order."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 5
components: ["agent/mutation-tester"]
evidence: ["removal round"]
watches: []
---

## Change

The mutation tester's prompt lost seventeen sentences and clauses that explained why a rule exists (1,169 words, was 1,418): the authorized-agent framing, the invented-mutation, global-lock, red-baseline, diff-hash, and SessionStart-guard reasons, the reasons behind the verdict order, the cull-verdict and no-test-can-kill notes, "do not soften", the Write/Edit and gate-bypass reasons, the routing notes, and the plausible-guess reason. Two clauses stay: "A previous run mutated a file and never restored it" at the lock check, and "it would also destroy the real uncommitted work in that file" at the restore.

## Evidence

removal round

### Anchor reasons

Anchor `agents/mutation-tester.md`, section `## Step 1 — Back up, hash, lock` (evidence: removal round):

Backup, content hash, and lock commands. Gone: the diff-hash reason and the SessionStart guard sentence.

Anchor `agents/mutation-tester.md`, section `## Step 2 — Apply the mutation` (evidence: removal round):

One Edit, exactly the given mutation, restore and report on a mismatch. Byte-identical in all arms. Not itself varied.

Anchor `agents/mutation-tester.md`, section `## Step 3 — Run and classify` (evidence: removal round):

The four verdicts with the executed-test check, the equivalence citation, and the distinguishing input. Gone: the reasons behind the order, the cull-verdict note, and the no-test-can-kill clause; verdicts matched in every run.

Anchor `agents/mutation-tester.md`, section `## Step 4 — Restore, on every path` (evidence: removal round):

Copy-back restore, hash verification, lock removal, the gate-block stop, and the mismatch stop. Kept: "it would also destroy the real uncommitted work in that file". Gone: the Write/Edit reason and the gate-bypass reason; no run restored with git, Write, or Edit.

Anchor `agents/mutation-tester.md`, section `## Hard limits` (evidence: removal round):

Never fix, never write a test, never commit, named mutations only, never report an unobserved outcome. Gone: the routing notes and the plausible-guess reason.

Anchor `agents/mutation-tester.md`, section `## Output Format` (evidence: removal round):

The report block. Byte-identical in all arms. Not itself varied.

## Result

A Go CLI with an uncommitted edit in the target file, in eight shapes: a killed mutant, a survivor, an equivalent mutant, a killer behind a build tag, a red baseline, a foreign lock, a mutation that does not match its line, and a dispatch with no test command; three Sonnet runs per wording per shape behind a dispatcher. Both wordings left every tree byte-identical, never touched the foreign lock, never restored with git, Write, or Edit, and stopped correctly on the build tag, red baseline, lock, and mismatch. The fully cut text took the uncommitted edit for a leftover mutation and stopped in two of twelve runs on the mutating shapes (full: none), which cost two verdicts and two restores. With the two clauses restored, twelve runs on the killed, survivor, and equivalent shapes gave the right verdict with a hash-verified restore every time, at 0.97x the full text's subagent fresh-plus-output tokens per run. Live gap, report-only, in every wording: with no test command in the dispatch, the agent guessed one and mutated in six of six runs.

## Watch

—

## Back-out

—
