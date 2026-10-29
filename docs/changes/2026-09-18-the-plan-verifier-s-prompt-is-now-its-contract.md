---
type: "Change"
change_type: "changed"
title: "The plan verifier's prompt is now its contract plus one rationale sentence"
description: "The plan verifier's prompt is now its contract plus one rationale sentence: the branch-end line (\"after `/review` converged every phase — correctness is looked at already."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/plan-verifier", "skill/review", "shared/plan-reading", "skill/fix"]
evidence: ["removal round"]
watches: []
---

## Change

The plan verifier's prompt is now its contract plus one rationale sentence: the branch-end line ("after `/review` converged every phase — correctness is looked at already. Not a second reviewer"), the boxed question, the scope table, the stale-dispatch rule, the three verdict definitions, the NOT-Doing skip, the denominator rule, the three acceptance-criteria verdicts with "behavior, not markers", the collects-and-runs rule, the dirty-Job-1 rule, both Job 2 sections with the checkbox formats, the write fence, the output block, and the three "not" bullets. Gone: "that gate is retired", the `plan-reading.md` phase-scoping aside, "a deliberate scope cut is not a gap", "'no drift' is not a result", the unverdictable-plan aside, "user-written behavior criteria, predating implementation", "a related-sounding name is not coverage", "you cannot detect narrowing by counting", the triage and phase-done parentheticals, "that is not behaviorally verified", the smoke-checklist accumulation line, "(gaps route to `/fix`)", the duplicate wrong-plan sentence, and one `/review` cross-reference.

## Evidence

removal round

### Anchor reasons

Anchor `skills/review/SKILL.md`, section `(preamble)` (evidence: removal round):

Frontmatter: name, description, and the allowed tools. Byte-identical in both arms.

Anchor `skills/review/SKILL.md`, section `## Modifiers` (evidence: removal round):

The modifier and specialist-flag pass-through lines. The "agent is unpinned" aside is gone: every run passed `model: sonnet` without it.

Anchor `skills/fix/SKILL.md`, section `(preamble)` (evidence: removal round):

Frontmatter: name, description, and the allowed tools. Byte-identical in both arms.

Anchor `agents/plan-verifier.md`, section `(preamble)` (evidence: removal round, census, judgment):

Frontmatter, the boxed question, the branch-end sentence ("after `/review` converged every phase — correctness is looked at already. Not a second reviewer") with the oracle/evidence line, and the never-verdict-from-checkboxes rule. The branch-end sentence is load-bearing: the wording without it read twice as many Go source and test files, ran the built binary a third more often, took 11% more turns, and used 1.2x the fresh tokens on the same trees; with it restored, all four returned to the full wording's level. The description is a routing line: what the agent is, who dispatches it, and any rule that the dispatcher needs. A census of this machine's top-level dispatches, a guide only, found none that menu text alone picked, and no dropped dispatcher rule had the description as its only home.

Anchor `agents/plan-verifier.md`, section `## Your scope` (evidence: removal round):

The scope line, the oracle table, the stale-dispatch rule, and "read plan + ticket in full". Gone: "that gate is retired" and the `plan-reading.md` phase-scoping aside. A stale `scope: phase` dispatch stopped with zero tool calls in every run of both wordings.

Anchor `agents/plan-verifier.md`, section `## Job 1 — Reconcile` (evidence: removal round):

The three verdict definitions, the `What We're NOT Doing` skip, and the denominator rule with its N/A line. Gone: "a deliberate scope cut is not a gap", "'no drift' is not a result", and the unverdictable-plan aside. The two decoy items under `What We're NOT Doing` were never verdicted or filed as gaps in any run of either wording.

Anchor `agents/plan-verifier.md`, section `### Acceptance-criteria coverage (when `docs/plans/<slug>/acceptance-criteria.md` exists)` (evidence: removal round):

The three coverage verdicts, "behavior, not markers" with "quote both", the collects-and-runs rule, and the dirty-Job-1 rule. Gone: "user-written behavior criteria, predating implementation", "a related-sounding name is not coverage", "you cannot detect narrowing by counting", the triage parenthetical, and "that is not behaviorally verified". A covered id naming its test, a manual-only id, and an untested id quoted as MISSING were all reported in every scored run of both wordings.

Anchor `agents/plan-verifier.md`, section `## Job 2 — Execute` (evidence: removal round):

Heading only. Byte-identical in both arms.

Anchor `agents/plan-verifier.md`, section `### Automated Verification — run every command` (evidence: removal round):

Run every listed command, record real output, fix nothing. Byte-identical in both arms; a `make check` or `go test` run appears in the agent transcript of every scored run.

Anchor `agents/plan-verifier.md`, section `### Manual Verification — drive what a terminal can, tag the rest` (evidence: removal round):

The clean-Job-1 gate, the two checkbox line formats, the no-browser rule, and the no-evidence rule. Gone: "they accumulate into `/verify`'s smoke-test checklist". On the clean tree every run that edited the plan wrote exactly 13 `agent-verified` and 1 `human-only` lines, in both wordings.

Anchor `agents/plan-verifier.md`, section `## Write scope — a hard fence` (evidence: removal round):

The fence: checkbox lines only, no code, never the criteria or status sections, never git. Gone: "(gaps route to `/fix`)", "(phase-done is your dispatcher's edit)", and "a wrong plan is a finding for the user" (its twin in the last bullet stays). No run of either wording changed a file other than the plan or a plan line other than a checkbox line.

Anchor `agents/plan-verifier.md`, section `## What this is not` (evidence: removal round):

The three "not" bullets. Gone: "`/review` converged" from the not-a-code-review bullet.

## Result

A Go CLI branch with its real nine-phase plan, seeded three ways: a gaps tree (spawn-depth grouping removed, the fixture README deleted, an acceptance-criteria file with one covered, one manual, and one untested id), a clean tree, and a stale phase-scoped dispatch; three Sonnet runs per wording per tree. The wording with every rationale sentence removed caught the same seeded gaps and gave the same acceptance-criteria verdicts, skipped the decoys, edited only checkbox lines, and stopped on the stale dispatch, but read twice as many source files, ran the binary a third more often, and used 1.2x the fresh tokens. Restoring the one branch-end sentence brought reads, binary runs, turns, and tokens back to the full wording's level (fresh+output 1.00x, tool calls 0.86x) with no catch lost. One live gap in every wording: the fixture-README criterion, which lives only in a plan phase and not in the ticket, was caught in about two runs of three.

## Watch

—

## Back-out

—
