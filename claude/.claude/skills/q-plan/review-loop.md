# QRSPI Review Loop (shared)

Every phase whose human gate was removed (Questions, Research) — plus the two that keep one (Design, Plan) — runs an automated quality review before its artifact flows downstream. This is the compensating control for the removed gates: an artifact is always checked by a human OR an agent, never neither. Reviews never wait on a human; they preserve flow while restoring the quality the gates used to provide. (Structure has no review of its own; its criteria are folded into the Plan checklist, which reviews the structure outline as an input.)

## The loop

1. **Review**: dispatch `qrspi-review` (omit `model`) with the artifact path, the phase's checklist (below), and the supporting paths allowed for that phase. It returns `PASS` or `ISSUES (k)`.
2. **PASS** → log (below) and proceed.
3. **ISSUES** → send the issue list back to the producer for ONE revision, then re-review:
   - Subagent producers — Research (`qrspi-research`), Plan (`qrspi-plan`): re-dispatch with the same inputs **plus** the issue list. A structural issue on a Plan review (phasing, verifiability) is fixed in the structure outline first, then the plan re-dispatched.
   - Inline producers — Design: you revise the artifact yourself against the issues.
   - **Max 2 revision rounds.**
4. **Still ISSUES after 2 rounds** → ESCALATE and log as `ESCALATED`:
   - Research / Plan: STOP and surface the remaining issues to the user.
   - Design: fold the remaining issues into the presentation you're about to show — the human is already looking.

## Isolation

Pre-design reviews (Research) are dispatched WITHOUT the ticket — pass ONLY the research file + questions file. Post-design reviews (Design, Plan) may include the ticket and any prior artifact. Never hand the research reviewer the ticket path.

## Logging (audit trail)

After every review verdict — **including the leak-check** — append one line to the QRSPI review log:

```
REVIEW_METRICS_FILE="$HOME/.claude/qrspi-review.jsonl" bash ~/.claude/skills/review/log-review-metrics \
  key=<TICKET> phase=<questions|research|design|plan> verdict=<PASS|ESCALATED> rounds=<n> issues=<m>
```

- `rounds` = revision rounds taken (`0` = clean first pass).
- `issues` = issue count in the FINAL review (`0` on PASS).
- Reuses the `/review` metrics script but writes a SEPARATE file, so `/review-stats` (code-finding severities) stays uncontaminated. Inspect with `jq . ~/.claude/qrspi-review.jsonl`.

## Per-phase checklists

**Research** — artifact `IQ-XXX-02-research.md`; inputs: research + questions files, **NO ticket**:

- Every question in the questions file is answered.
- Every claim carries a `file:line` reference that actually resolves and says what's claimed (spot-verify with Grep/Read).
- Zero speculation, opinion, or implementation suggestion — findings only.

**Design presentation** — artifact = the drafted presentation; inputs: draft + research + ticket:

- Every `file:line` / pattern reference resolves.
- Each design question presents ≥2 genuine alternatives — not a foregone conclusion dressed as a question.
- The counter-priming names 3 real, distinct out-of-scope approaches (not strawmen).
- No implementation/phase detail leaking in (that belongs to Structure/Plan).

**Plan** — artifact `IQ-XXX-05-plan.md`; inputs: plan + structure + design + ticket:

- Phases are VERTICAL (each an end-to-end slice), not horizontal layers.
- Each phase is independently verifiable and leaves the system working.
- Each phase states a concrete, testable "what becomes true after this" — no vague "implement X".
- Every Success Criterion is a testable assertion naming a real project verification command.
- Every Phase Status line has a `(risk: low|high)` tag, and each tag is defensible against the rubric (high = migrations/data mutation, auth/security, public API contracts, irreversible ops, cross-service). A dubious `low` is an issue — it's what `/code` auto-advances past without a human.
- If the ticket is behavioral, Acceptance Stubs exist with a real count command, and the final phase's Automated Verification includes that command returning zero.
