---
name: deep-plan
description: Run the full deep-plan pipeline (Questions → review → leak-check → Research → Design → Structure → Plan) in one orchestrated session. Routes artifact file paths between subagents; preserves Q→R isolation structurally instead of relying on /clear discipline.
allowed-tools: [Bash, Read, Glob, Agent, AskUserQuestion, Edit, Write]
---

# deep-plan Orchestrator

You are a router. Until Phase D begins, you NEVER read, summarize, or paraphrase the ticket, the questions, or any artifact — you move file paths between subagents. If you are about to read one before Phase D: stop, pass the path instead. Naming the goal in your own output before research completes contaminates every downstream step.

## Phase 0 — Resolve

1. Run `bash ~/.claude/scripts/resolve-task-dir.sh "$ARGUMENTS"`. Exit 0 → that is `DIR`. Exit 3 → ask the user which. Exit 4 → no `DIR` yet; get the ticket onto disk, then hand its path to Phase Q (which creates `DIR` if absent). **Never pre-copy the ticket into `DIR`** — Phase Q snapshots the source to `<KEY>-00-ticket.md`, so a stray sibling there becomes a duplicate. If the user has a ticket file, pass that path **as-is**. If they only have a Jira key/URL, fetch it per `~/.claude/skills/_shared/jira-ticket.md` (required-ticket caller; neither `/pull-ticket` nor the Jira tools persist a file on their own) and `Write` it verbatim straight to the canonical path `docs/eng-specs/<KEY>-<slug>/<KEY>-00-ticket.md` per that file's persistence rule: raw fields only, no paraphrase or goal words in your context.
2. Glob `DIR/*.md` (filenames only — do not read). If artifacts already exist, ask which phase to resume from and skip completed phases. **A questions file on disk does NOT mean its two checks ran** — they leave no numbered artifact, so a run that died mid-Phase-Q looks identical to one that finished it. Resuming at Phase R or later: re-run both checks first. They are idempotent, and a clean set passes twice for the price of one review — cheap insurance against silently researching an ungated question set.

## Phase Q — Questions (subagent)

Dispatch `deep-plan-questions` (omit `model`) with ONLY: the ticket path and the task directory (or slug). No other context. It returns the questions file path.

## Questions review, then leak-check (subagents, in this order)

**Quality first.** Dispatch `deep-plan-questions-review` (omit `model`) with the ticket path, the questions path, and a findings path (`DIR/.questions-review.md`). It returns ONLY `PASS — …` or `ISSUES (k of N) → <path>`. On ISSUES: re-dispatch `deep-plan-questions` with that **path** — **never open it; it names the goal, and reading it is the isolation breach this whole ordering exists to prevent** — then re-review. One revision round; if the second verdict is still ISSUES, proceed to leak-check anyway and tell the user the bare count (never the findings text — it names the goal). This gate informs, it never stops. Log `phase=questions` per `${CLAUDE_SKILL_DIR}/review-loop.md`.

**Then leak-check.** Dispatch `deep-plan-leak-check` (omit `model`) with ONLY the questions path; it returns `PASS` or a flagged list with intent-free rewrites. If flagged: auto-apply without asking — re-dispatch `deep-plan-questions` with the flagged items + rewrites, then re-check. Max 2 rounds; still flagged after 2, proceed to research and note the residual flags (informational, not a stop). It runs LAST so that anything the quality review added gets laundered before research sees it. No human gate: questions → review → leak-check → research flows straight through. Log `phase=leak-check` (`issues` = flagged questions, `rounds` = rewrite rounds) per `${CLAUDE_SKILL_DIR}/review-loop.md`.

## Phase R — Research (subagent)

Dispatch `deep-plan-research` (omit `model`) with ONLY the questions file path and the task directory. The dispatch prompt must not mention the ticket, its path, or anything goal-shaped. It returns the research file path.

Then run the review loop (`${CLAUDE_SKILL_DIR}/review-loop.md`, **Research** checklist) — pass the reviewer ONLY the research + questions files, never the ticket. This gates the flow into Design.

## Phase D — Design (inline, interactive)

Research is on disk; isolation no longer applies — you become a participant. Read `${CLAUDE_SKILL_DIR}/design-phase.md` and follow it.

## Phase S — Structure (inline, interactive)

Read `${CLAUDE_SKILL_DIR}/structure-phase.md` and follow it.

## Phase P — Plan (subagent)

Dispatch `deep-plan-planner` (omit `model`) with ONLY the task directory. It reads the artifacts itself and returns the plan path, plus any `DESIGN GAPS` it hit.

Then run the review loop (`${CLAUDE_SKILL_DIR}/review-loop.md`, **Plan** checklist) before the gate — this is what defends the risk tags `/code` auto-advances on.

**Design gaps** (from the planner, or the reviewer's decision-trace check). The plan you were handed contains the planner's own best guess at each gap, marked `<!-- DESIGN GAP: ... -->`. Do not present it. Round trip:

1. Resolve each gap with the user (AskUserQuestion — options, your recommendation, what breaks if it's wrong).
2. Write each answer into `IQ-XXX-03-design.md` as a decision block with its owner tag. The design doc is the ledger; a choice settled after the design gate otherwise belongs to no one.
3. **Re-run the Design document review** on the edited design doc (`phase=design-doc`). You just hand-wrote blocks into the ledger the owner tags are audited against; the Plan checklist only asks whether the plan traces to a block, never whether the block is well-formed. Skip this and a malformed or mis-tagged block ships unread — and the alarm's count is recomputed here, not there.
4. **Re-dispatch `deep-plan-planner`** with the updated design doc and the resolutions. Do NOT hand-patch the plan — the planner's guess may have shaped phases and success criteria well beyond the marked line, and the markers must be gone from the final artifact.
5. **Re-run the Plan review** on the regenerated plan. Its decision-trace check is what confirms the plan now matches the ledger.

**Termination.** A resolution can force a fresh gap (settling A exposes B). Loop back to 1 — at most **twice**. If a third round surfaces new gaps, stop and tell the user plainly: the design doc is underspecified for this ticket, and the honest fix is a Phase D pass, not another lap. Never present a plan carrying a live `DESIGN GAP` marker.

If the user's answer matches the planner's guess exactly, 3–5 still run — the plan is cheap to regenerate and a stale marker in a shipped plan reads as an unresolved decision to everyone downstream.

## Gate — human (MANDATORY)

Stop. Say: "Plan written → `<path>`. Review it — the Acceptance Stubs sentences are the highest-leverage lines. Confirm to complete deep-plan." Do NOT show the footer without explicit confirmation. If the user requests changes, route corrections back through Phase S or re-dispatch `deep-plan-planner`, then return to this gate.

## Footer

```
Saved → <plan path>
deep-plan complete. Next: /clear, then /code <plan path>
Spot-check the plan — the Acceptance Stubs sentences are the highest-leverage lines in it; save deep review for the actual code. After the code ships: /verify confirms the plan was fully built, then you open the PR, then /finalize collapses the folder into an ADR.
```

## Hard Rules

- This file stays ≤80 lines. If an edit pushes past, the addition belongs in a phase file or an agent — not here.
- No reading artifact contents before Phase D — including the questions-review findings file, which is the newest and most plausible-looking way to break this rule. No goal words in the Q, review, leak-check, or R dispatch prompts.
- Every dispatch omits `model` — every `deep-plan-*` agent pins its own.

## Arguments

$ARGUMENTS
