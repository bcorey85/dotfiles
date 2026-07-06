# Phase S — Structure (inline playbook)

Create a concise structure outline describing HOW to implement the approved design — C-header-style: signatures, types, and phase boundaries, not full code.

## Inputs

The ticket, research, and design docs are already in context from Phase D. Re-read `DIR/IQ-XXX-03-design.md` only if it was edited during review.

## Vertical, not horizontal

WRONG (horizontal): Phase 1 all DB → Phase 2 all services → Phase 3 all API → Phase 4 all UI. 1200 lines before anything is testable.

RIGHT (vertical): Phase 1 = feature slice A end-to-end (DB + service + API + UI), Phase 2 = slice B, Phase N = edge cases + polish. Each phase independently verifiable; if Phase 2 breaks, Phase 1 still works.

## Decide the phasing (no user gate)

Structure runs automatically — do NOT stop for approval. Break the work into vertical phases yourself, applying the vertical-not-horizontal rule above. If the design doc leaves the phasing genuinely ambiguous, make the most reasonable call and record it as an assumption in the outline rather than pausing. The human review point is the Plan gate that follows.

## Write the Outline (~2 pages max)

Save to `DIR/IQ-XXX-04-structure.md`:

```markdown
# Structure Outline: [Feature Name]

**Ticket**: DIR/IQ-XXX-00-ticket.md (IQ-XXX)
**Design**: DIR/IQ-XXX-03-design.md
**Date**: YYYY-MM-DD

## Phase 1: [Name] — [what this achieves]

**Scope**: [which vertical slice]
**Key changes**:

- `[file/component]`: [what changes — new types, signatures, or brief description]
  **Verification**: [how to confirm this phase works]

---

## Phase N: Testing & Polish

**Scope**: edge cases, error handling, cleanup
**Key changes**: [tests, error handling]
**Verification**: project verification command passes + manual scenarios
```

## When to Add Detail

If the implementing agent might get a phase wrong, expand it with specific types and signatures (e.g. `types.ts: add EmailNotification { recipient: string; template: string }`). Keep confident phases high-level; expand only where ambiguity is risky.

## What NOT To Do

- Do NOT write full implementation code — signatures and types only where needed.
- Do NOT create horizontal phases.
- Do NOT stop for user approval — structure flows straight into Plan; review happens at the Plan gate.
- Do NOT exceed ~2 pages — longer means phases are too detailed.
- Do NOT re-debate design decisions — those are resolved.

## Review before Plan (MANDATORY)

Structure has no human gate, so this review is its only quality check before it flows into Plan. After writing the outline, run the review loop (`${CLAUDE_SKILL_DIR}/review-loop.md`, **Structure** checklist; inputs: structure + design docs). Fix what it flags (max 2 rounds); if it still fails, STOP and surface the issues to the user — an unresolvable structure problem is the one thing worth interrupting the auto-flow for. Log the verdict (`phase=structure`).

When the review passes, continue directly to Phase P (no `/clear`).
