# Phase S — Structure (inline playbook)

Create a concise structure outline describing HOW to implement the approved design — C-header-style: signatures, types, and phase boundaries, not full code.

## Inputs

If Phase D ran in THIS session, the ticket, research, and design docs are already in context — re-read `DIR/IQ-XXX-03-design.md` only if it was edited during review.

**If you are resuming** (Phase 0 found existing artifacts and the user resumed at S, so Phase D ran in an earlier session), read `DIR/IQ-XXX-00-ticket.md`, `DIR/IQ-XXX-02-research.md`, and `DIR/IQ-XXX-03-design.md` FULLY (no limit/offset) before phasing anything. The Q→R isolation rule that forbade reading these does NOT apply here — it ends at Phase D, and you are downstream of it. Phasing work you have not read the design for is how a phase quietly re-decides something the design already settled, and the rule below ("Design is not yours") is unenforceable if you never read what the design said.

**On resume, the design doc's existence is not evidence that Phase D ran.** Phase 0 detects it by filename alone, and a file can be stale, hand-authored, or abandoned mid-phase. Before you treat it as the ledger, confirm it looks like a Phase D output: `## Framing` present with the user's own words, and every decision block carrying one of the three owner tags. If either is missing, STOP and tell the user what you found — offer to re-run Phase D. Do not fill the gaps yourself and do not phase against it anyway: an unowned design doc launders whatever is in it into "approved," which is the precise failure the owner tags exist to make impossible.

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

## Decisions the design doesn't settle (the one thing that DOES stop you)

Phasing is yours. **Design is not.** The owner tags in the design doc are only worth something if the design doc is the whole ledger — a decision the user never saw, made here because structuring forced the question, is an untagged decision that no alarm can ever catch. Phase D's framing pass buys nothing if the real choice gets made in Phase S.

The bar is the decision block, not the feeling of uncertainty: **would this choice need a `Choice / Reasoning / Alternatives rejected / Trade-off accepted` block?** That means two or more viable approaches with a user-visible consequence — a data shape, a contract, a failure mode, a retention or security behavior. It does NOT mean phase ordering, slice boundaries, naming, or how much detail a phase carries. Those are structuring, and structuring is your job.

When a choice clears that bar:

1. **Stop.** Do not pick the reasonable one and note it as an assumption — an assumption is what you record when the answer doesn't matter, and if it cleared the bar it matters.
2. Ask the user directly (AskUserQuestion) — one question, framed with the options and your recommendation, as in Phase D.
3. Write the resolution back into `DIR/IQ-XXX-03-design.md` as a proper decision block with its owner tag. The design doc is the ledger; the outline is not.
4. Then continue phasing.

This should be rare — Phase D is supposed to have drained these. If it happens more than once or twice on a task, that is a signal the design phase under-explored, worth saying out loud to the user.

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
- Do NOT make NEW ones either. Re-debating a settled decision and quietly settling an unsettled one are opposite errors with the same cause: treating the design doc as advisory. It is the ledger. If structuring surfaced a real choice, it goes back to the user and into the doc — see the section above.

## No separate review

Structure flows straight into Phase P (no `/clear`, no review dispatch). Its
quality criteria — vertical phases, independently verifiable slices, a
concrete "what becomes true" per phase — are enforced at the Plan review,
which receives this outline as an input.
