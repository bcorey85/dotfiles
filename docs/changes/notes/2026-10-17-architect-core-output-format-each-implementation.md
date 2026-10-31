---
type: "Change"
change_type: "changed"
title: "`architect-core` Output Format: each implementation step ends with a `Reuse:` line"
description: "`architect-core` Output Format: each implementation step ends with a `Reuse:` line."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-17T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["skill/architect-core", "shared/plan-format", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
---

## Change

`architect-core` Output Format: each implementation step ends with a `Reuse:` line. It names every existing unit that the step's code must call, with its path: helpers, constants, error codes, lookups, test factories. The unit goes at the step even when `## Reuse Map` lists it, and an empty line says where the architect searched. The spec template tells the synthesis to keep the line in each phase's Changes Required. The same rule in `_shared/plan-format.md` was blocked by the eng-spec word budget, because that load is 1,561 words against a 1,500 ceiling

## Evidence

judgment

### Anchor reasons

Anchor `agents/spec-research.md`, section `## Document format` (evidence: unproven):

The frontmatter fields, the topic derived from the questions rather than a ticket, and the four required sections including the reuse inventory a downstream architect seeds its own map from. Never varied.

Anchor `agents/frontend-architect.md`, section `## Plan Body Sections (frontend)` (evidence: unproven):

The frontend plan template and its insertion point, including the reuse map seeded from the research document's inventory and the rule that every new unit carries a justification line. That justification line is called the gate and no round has checked whether it holds one.

## Result

Not yet measured. In one plan, the global reuse list named the money-sum helper, and the payments phase did not. Both builds from that plan wrote their own sum, and an error code was typed inline at 4 sites. Review fixed both copies in both builds.

## Watch

review findings of class `duplication` per review run

## Back-out

—
