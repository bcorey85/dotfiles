# deep-plan Review Loop (shared)

Every phase whose human gate was removed runs an automated check before its artifact flows downstream. This is the compensating control for the removed gates: an artifact is always checked by a human OR an agent, never neither. Reviews never wait on a human; they preserve flow while restoring the quality the gates used to provide.

Which check guards what:

| Artifact | Guarded by |
| --- | --- |
| Questions | `deep-plan-leak-check` (intent-leak only — see the gap below) |
| Research | `deep-plan-review`, **Research** checklist |
| Design presentation | `deep-plan-review`, **Design presentation** checklist (`phase=design`) |
| Design document | `deep-plan-review`, **Design document** checklist (`phase=design-doc`) |
| Structure | nothing of its own — criteria folded into the Plan checklist, which takes the outline as an input (gate cut 2026-07-07 on metrics) |
| Plan | `deep-plan-review`, **Plan** checklist, then the human gate |

**Known gap — the questions set has no quality review.** Leak-check asks only "does this question leak the goal?", never "are these the RIGHT questions?" — and a bad question set silently caps the quality of the research built on it. There is no `Questions` checklist below and no `deep-plan-review` dispatch in Phase Q; `phase=questions` survives in the log enum only to read historical entries, which additionally CONFLATE leak-check (see `DESIGN.md`). Adding a real gate here is a cost decision the user has not made — do not invent one mid-run; if the question set looks wrong, say so to the user rather than silently patching it.

## The loop

1. **Review**: dispatch `deep-plan-review` (omit `model`) with the artifact path, the phase's checklist (below), and the supporting paths allowed for that phase. It returns `PASS` or `ISSUES (k)`.
2. **PASS** → log (below) and proceed.
3. **ISSUES** → send the issue list back to the producer for ONE revision, then re-review:
   - Subagent producers — Research (`deep-plan-research`), Plan (`deep-plan-planner`): re-dispatch with the same inputs **plus** the issue list. A structural issue on a Plan review (phasing, verifiability) is fixed in the structure outline first, then the plan re-dispatched.
   - Inline producers — Design: you revise the artifact yourself against the issues.
   - **Max 2 revision rounds.**
   - **Two findings are exempt from this machinery — see "Findings you may not revise away" below.** Revision is the wrong verb for both, and running them through the loop actively corrupts them.
4. **Still ISSUES after 2 rounds** → ESCALATE and log as `ESCALATED`. The remedy depends on whether a human is about to look at the artifact anyway:
   - **Research / Plan / Design document (`phase=design-doc`)**: STOP and surface the remaining issues to the user, then resume at whatever step dispatched this review. For `design-doc` specifically there is no presentation left to fold into — it already happened, and nothing downstream of it gates without one — so this is a genuine stop, in the same one-line form as the ratification alarm. (The design-doc review has two callers: Phase D, and Phase P's design-gap round trip. Do not hard-code "next is Phase S" — from the round trip, Phase S is already behind you.)
   - **Design presentation (`phase=design`)**: fold the remaining issues into the presentation you're about to show — the human is already looking, so the cheapest correct move is to show them the flaws alongside it. This is the ONLY checkpoint where "fold it in" is executable, and it does not apply to the missing-framing finding below.

## Findings you may not revise away

The loop assumes a finding is a defect in the artifact that the producer can fix. These two are not, and treating them as ordinary issues turns each into its own failure:

- **The ratification alarm** (`design-doc` checklist) — a report about WHO designed the artifact, not a flaw in it. Never revise, never block: report, log, carry the canonical line to the user. Owned by `~/.claude/skills/_shared/design-decision-format.md` § The ratification alarm.
- **"The framing was never collected"** (`design` checklist) — the user's Step 0 answer cannot be reconstructed by revising a draft, because it is not in the draft; it is in a conversation that never happened. Do NOT revise, do NOT spend a round, do NOT escalate, and above all do NOT fold it into the presentation and show it — the presentation is the very thing that must not exist yet. **STOP, go run Step 0 of `design-phase.md`, then re-draft from the user's answer and re-review.** This does not consume a revision round; the draft that skipped the framing is discarded, not repaired. This is the one invariant the whole design phase exists to protect, and a draft written without it is not a flawed artifact — it is the failure itself.

  **The reviewer reports it; YOU decide what it means.** The reviewer sees only the draft — a missing `Your approach — my verdict` section looks identical whether the framing pass never ran or ran and you forgot to quote it. It cannot tell those apart and is not asked to: it reports `FRAMING-MISSING` whenever the section is absent, every time. **You are the one who knows whether Step 0 ran, because you either had that conversation or you didn't.** Read the verdict against that memory:

  - **Step 0 never ran** → the stop above. Go collect the framing, re-draft, re-review. No round consumed.
  - **Step 0 ran and you have the user's answer** → this is a drafting slip, not a missing framing pass. The answer is in your context; put it in the draft. Ordinary revisable issue, under the normal 2-round cap. **Do not re-run Step 0 and do not ask the user the same three questions twice** — re-asking is its own harm: it teaches the user the framing pass is ceremony.

  So it stops the phase at most once. Step 0 either ran or it didn't, and once you have the user's answer you cannot un-have it.

## Isolation

Pre-design reviews (Research) are dispatched WITHOUT the ticket — pass ONLY the research file + questions file. Post-design reviews (Design, Plan) may include the ticket and any prior artifact. Never hand the research reviewer the ticket path.

## Logging (audit trail)

After every review verdict — **including the leak-check** — append one line to the deep-plan review log:

```
REVIEW_METRICS_FILE="$HOME/.claude/deep-plan-review.jsonl" bash ~/.claude/skills/review/log-review-metrics \
  key=<TICKET> phase=<questions|leak-check|research|design|design-doc|plan> verdict=<PASS|ESCALATED> rounds=<n> issues=<m>
```

- `rounds` = revision rounds taken (`0` = clean first pass).
- `issues` = issue count the FIRST review returned — what the gate caught
  (`0` = clean first pass). This is the per-gate value signal; do not log
  the final-round count, which is 0 on every PASS by construction.
- Leak-check: log `phase=leak-check` with `issues` = questions flagged as
  materially intent-leaking, `rounds` = rewrite rounds taken.
- `phase=design` is the presentation review (pre-questions); `phase=design-doc`
  is the written design review (post-questions, where the ratification alarm
  fires). They are separate lines — collapsing them loses the alarm's history,
  which is the only longitudinal signal on whether the framing pass is working.
- Reuses the `/review` metrics script but writes a SEPARATE file, so `/audit review` (code-finding severities) stays uncontaminated. Inspect with `jq . ~/.claude/deep-plan-review.jsonl`.

## Per-phase checklists

**Research** — artifact `IQ-XXX-02-research.md`; inputs: research + questions files, **NO ticket**:

- Every question in the questions file is answered.
- Every claim carries a `file:line` reference that actually resolves and says what's claimed (spot-verify with Grep/Read).
- Zero speculation, opinion, or implementation suggestion — findings only.

**Design presentation** — artifact = the drafted presentation; inputs: draft + research + ticket:

- Every `file:line` / pattern reference resolves.
- **The user's framing was collected before the draft existed** — the presentation carries a `Your approach — my verdict` section quoting the user's Step 0 answer. A draft written without one means the agent went first, which is the failure this phase exists to prevent. **Report this as `FRAMING-MISSING`, not as an ordinary issue** — it is not revisable, and the loop's exemption above tells the producer to stop and go collect the framing rather than repair the draft.
- **The verdict on the framing is honest** — where research contradicts the user's approach, the presentation says so plainly and leads with it. A verdict of "sound" on an approach the research undercuts is the worst possible failure here: it launders the agent's design as the user's.
- Each design question is framed against the user's approach per the three-case rule in `design-phase.md` (supports → state and move on; breaks → lead with the failure; silent → genuine menu with a recommendation). A question that re-elicits an approach the user already named is an issue.
- Where a question IS a genuine menu, it presents ≥2 real alternatives — not a foregone conclusion dressed as a question.
- The counter-priming names 3 real, distinct out-of-scope approaches (not strawmen).
- No implementation/phase detail leaking in (that belongs to Structure/Plan).

**Design document** — artifact `IQ-XXX-03-design.md`; inputs: design + research + ticket:

- `## Framing` is present and quotes the user's Step 0 answer verbatim, with the agent's verdict on it.
- Every decision block has all four fields, and the owner tag is exactly one of `User-originated` / `User-ratified` / `Locked`. A bare `(User)` is an issue — it hides whether the user designed the decision or accepted it.
- **Ratification alarm** — read `~/.claude/skills/_shared/design-decision-format.md` § The ratification alarm and apply it exactly as written: it owns the threshold, both fire conditions (zero-originated and zero-decision), and the report lines. Report the full owner-tag distribution with your verdict. Do not restate or reinterpret the threshold in this checklist.
- Each `(User-originated)` tag is defensible under the § Owner tags tests — the user's input demonstrably changed the outcome. It usually traces to a line in `## Framing`, but need not: overriding the agent's recommendation, or materially editing what it proposed, also originates, and neither leaves a mark in Framing. What you are checking is that SOMETHING the user did is visible in the outcome. A tag with nothing behind it is mislabeled ratification — worse than an honest `(User-ratified)`, because it defeats the alarm.
- **Scope-only rejections** (`design-decision-format.md` § Rules) — scan every `Alternatives rejected` field for an option turned down SOLELY on scope grounds ("not requested", "out of scope", "scope creep") rather than a named technical failure mode. Each must be marked as needing the user's explicit sign-off, never resolved by a default. Scope is the ticket-owner's call, and this lane has twice declined the right alternative on scope discipline and reproduced a real regression.
- **External Contracts evidence class** (`design-decision-format.md` § External Contracts rule) — where the change alters what an external tool ACCEPTS or ENFORCES at runtime, each acceptance claim states `exercised` or `declared-only`. A claim resting on declared-only evidence (schema text, in-repo precedent, vendored docs) with no staged step that exercises the real tool is an issue.
- **Counter-priming survived into the document** — the three out-of-scope approaches from the presentation appear under `## Approaches Considered and Not Taken`, each with a named failure mode. Three approaches surfaced at the gate and then silently dropped from the artifact is an issue: the design doc is what `finalize`/`/adr` distills, and an alternative that leaves no trace there is one the next reader will re-propose. (Exception, per `design-phase.md`: the agent explicitly said it could not name three. Then the document says that, and says how many it named. That admission is diagnostic about how narrowly the research framed the space — it must survive into the artifact too, not be quietly rounded up to three.)

**Plan** — artifact `IQ-XXX-05-plan.md`; inputs: plan + structure + design + ticket:

- **Decision trace (the owner tags mean nothing without this).** Every design-level choice the plan commits to traces back to a decision block in the design doc, and none of them contradicts one. A choice that meets the decision-block bar — two or more viable approaches with a user-visible consequence (data shape, contract, failure mode, retention/security behavior) — and appears nowhere in the design doc is an **unflagged design gap**, and it is a finding whether or not the plan is otherwise good. It is a decision the user's design gate never saw and no owner tag covers. Tactical detail (import paths, test placement, helper names, phase wording) is explicitly NOT in scope for this check — the planner is supposed to settle those.
- Design gaps the planner DID flag (`<!-- DESIGN GAP: ... -->` / its `DESIGN GAPS` list) are not issues — they worked. Report them so the orchestrator carries them to the user; do not try to resolve them.
- Phases are VERTICAL (each an end-to-end slice), not horizontal layers; Phase 1 is the thinnest end-to-end skeleton. A single-layer phase is legitimate only for genuinely infra-only work and must state `Manual Verification: N/A (infra-only)`.
- Each phase is independently verifiable and leaves the system working.
- Each phase states a concrete, testable "what becomes true after this" — no vague "implement X".
- Every Success Criterion is a testable assertion naming a real project verification command.
- Every Phase Status line has a `(risk: low|high)` tag, and each tag is defensible against the rubric (high = migrations/data mutation, auth/security, public API contracts, irreversible ops, cross-service). A dubious `low` is an issue — it's what `/code` auto-advances past without a human.
- If the ticket is behavioral, Acceptance Stubs exist with a real count command, and the final phase's Automated Verification includes that command returning zero.
- The four mandatory closing phases (`~/.claude/skills/_shared/closing-phases.md`) are present, in order, after the last feature phase: Refactor pass, Verify pass, Orient pass, Finalize (`/finalize` for this lane). Missing or reordered is an issue.
