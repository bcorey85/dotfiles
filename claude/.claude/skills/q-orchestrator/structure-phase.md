# Phase S — Structure (inline playbook)

Create a concise structure outline describing HOW to implement the approved design — C-header-style: signatures, types, and phase boundaries, not full code.

## Inputs

The ticket, research, and design docs are already in context from Phase D. Re-read `DIR/IQ-XXX-03-design.md` only if it was edited during review.

## Vertical, not horizontal

WRONG (horizontal): Phase 1 all DB → Phase 2 all services → Phase 3 all API → Phase 4 all UI. 1200 lines before anything is testable.

RIGHT (vertical): Phase 1 = feature slice A end-to-end (DB + service + API + UI), Phase 2 = slice B, Phase N = edge cases + polish. Each phase independently verifiable; if Phase 2 breaks, Phase 1 still works.

## Initial Presentation (MANDATORY)

```
Here's how I'd break this into vertical phases:

Phase 1: [Name] — [one sentence: what becomes testable after this]
Phase 2: [Name] — [one sentence]
Phase N: Testing & Polish

Does this ordering make sense? Should any phases be split, merged, or reordered?
```

Wait for approval. Iterate until the user approves ordering and scope.

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
- Do NOT skip user review — present and iterate.
- Do NOT exceed ~2 pages — longer means phases are too detailed.
- Do NOT re-debate design decisions — those are resolved.

When saved, continue directly to Phase P (no `/clear`).
