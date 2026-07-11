# Phase S — Structure (inline playbook)

Create a concise structure outline describing HOW to implement the approved design — C-header-style: signatures, types, and phase boundaries, not full code.

## Inputs

The ticket, research, and design docs are already in context from Phase D. Re-read `DIR/IQ-XXX-03-design.md` only if it was edited during review.

## Vertical, not horizontal

WRONG (horizontal): Phase 1 all DB → Phase 2 all services → Phase 3 all API → Phase 4 all UI. 1200 lines before anything is testable.

RIGHT (vertical): Phase 1 = feature slice A end-to-end (DB + service + API + UI), Phase 2 = slice B, Phase N = edge cases + polish. Each phase independently verifiable; if Phase 2 breaks, Phase 1 still works.

## Contracts first, skeleton second

Vertical slices need two special phases in front (pattern: spec-kit `/plan` emits `data-model.md` + `contracts/` before any tasks; walking skeleton per Cockburn):

- **Phase 0 — Contracts**: the shared surface only — TS types, schemas, API shapes, DB migration sketches — as actual committable content in the outline, not prose describing it. This is C-header-style already, so it belongs here. Rationale: the human reviews contracts at the Plan gate in the same sitting as the plan itself, and approval **freezes** them — implementing agents treat Phase 0 files as read-only; needing to change one mid-phase is a stop-and-surface event, never a silent edit. Front-load ONLY the coordination surface between slices/streams; internal design stays inside its slice (freezing more is BDUF).
- **Phase 1 — Walking skeleton**: the thinnest end-to-end path that exercises every Phase 0 contract. Paper contracts are hypotheses; the skeleton falsifies wrong ones in hours instead of at integration. Agents left alone build big layers in isolation — this phase is the explicit countermeasure. `/code` always stops after Phase 1 for calibration, so a skeleton Phase 1 puts the full wiring in front of that mandatory human stop instead of one layer's internals.
- **Phases 2..N**: remaining slices in dependency order (no-dependency slices first). Parallel coder fan-out is allowed only AFTER the skeleton phase is merged — the skeleton is what proves the contracts the streams will code against.

## Decide the phasing (no user gate)

Structure runs automatically — do NOT stop for approval. Break the work into vertical phases yourself, applying the vertical-not-horizontal rule above. If the design doc leaves the phasing genuinely ambiguous, make the most reasonable call and record it as an assumption in the outline rather than pausing. The human review point is the Plan gate that follows.

## Write the Outline (~2 pages max)

Save to `DIR/IQ-XXX-04-structure.md`:

```markdown
# Structure Outline: [Feature Name]

**Ticket**: DIR/IQ-XXX-00-ticket.md (IQ-XXX)
**Design**: DIR/IQ-XXX-03-design.md
**Date**: YYYY-MM-DD

## Phase 0: Contracts

**Scope**: shared types / schemas / API shapes / migration sketches — the coordination surface, frozen at Plan approval
**Content**: [the actual contract code, committable as-is]

---

## Phase 1: Walking skeleton

**Scope**: thinnest end-to-end path exercising every Phase 0 contract
**Verification**: [the one scenario that proves the contracts hold at runtime]

---

## Phase 2: [Name] — [what this achieves]

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

## No separate review

Structure flows straight into Phase P (no `/clear`, no review dispatch). Its
quality criteria — vertical phases, independently verifiable slices, a
concrete "what becomes true" per phase — are enforced at the Plan review,
which receives this outline as an input.
