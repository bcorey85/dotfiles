---
name: code
description: Dispatch coder subagent(s) for implementation, then auto-run `/review` — auto-detects scope or accepts be/fe/fs modifier
allowed-tools: [Agent, Read, Glob, Grep, Skill]
---

# Code

Dispatch coder subagent(s) to implement code directly without architectural planning.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope
- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). `+fast` for trivial tasks (renames, typos, one-liners); `+deep` for complex tasks requiring deeper reasoning.

## Instructions

1. **Check for modifiers**: If `+deep` is present, swap each coder for its `-deep` variant and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Detect multi-phase plans (MANDATORY check)**: If the task input is a path to a plan file (e.g., `*-plan.md` under `docs/eng-specs/`) or pasted plan content, read it and check whether it contains multiple `## Phase N:` sections.

   **If it's a multi-phase plan:**
   - Do NOT dispatch all phases at once.
   - Identify the next un-executed phase by reading the plan's `## Phase Status` section: the first unchecked (`- [ ]`) entry is the phase to dispatch. This is the source of truth across `/clear` boundaries — do NOT scan git log or diff to figure out where you are. If the plan has no `## Phase Status` section (older plan format), fall back to `git status` + per-phase success criteria, but flag this to the user so they can backfill the section.
   - Dispatch the coder for THAT ONE PHASE ONLY. The coder must run the phase's "Automated Verification" gate (typically `npm run validate` or equivalent) before returning.
   - After the coder completes and you summarize, auto-dispatch `/review` (step 5).
   - **Drift gate** — after `/review` converges, before marking the phase done: dispatch ONE read-only reconciliation agent (`subagent_type: "general-purpose"`, `model: "sonnet"`) with ONLY the plan path, the phase number, and the handoff file list. It verdicts each of the phase's `Success Criteria` items `done` / `partial` / `missing` against the actual diff (file:line evidence; changes nothing). If the plan has an `Acceptance Stubs` section, it also verifies stub-sentence survival: every stub sentence must still exist — as a todo or as a real test bearing that name. A reworded or deleted stub is tampering; report it as `missing`. This is the phase-scoped version of `/q-verify` — it catches plan drift while it is still phase-sized. Clean → proceed. Any `partial`/`missing` → do NOT mark the phase done; dispatch `/fix` once with the gaps as the issue list, then re-run the drift gate once. Still dirty → stop and hand the remaining gaps to the user.
   - **Behavioral verification (agent-executed)** — after the drift gate is clean: if the phase has `Manual Verification` items, dispatch ONE `general-purpose` agent (`model: "sonnet"`) with the plan path, the phase number, and the items. It executes every item it can drive from the terminal — curl the endpoint, run the CLI, execute the scenario command. For UI flows: **scripted Playwright, NEVER the Playwright MCP** (the MCP holds a live browser session with per-action tool calls and accessibility-tree payloads — too expensive; a script compresses the whole flow into one Bash call whose only context cost is what it prints). Form: write a throwaway `/tmp/verify-phase<N>.mjs` using the plain `playwright` library (launch → drive → print assertions → exit code), run it once, keep the printed output as evidence; `npx playwright screenshot <url> /tmp/<name>.png` for render checks; screenshots always to `/tmp`, never the repo. Browser items only when the project already has Playwright installed — never install browsers to verify; tag those items `human-only` instead. It edits the plan in place: `- [x] agent-verified: <item> — <evidence: command + observed result>`, or `- [ ] human-only: <item> — <why it can't be driven>`. It changes NO code, and it never checks an item without captured evidence — observed output, not asserted success. Human-only remainders accumulate for the end-of-feature review packet (`/q-verify`).
   - After peer review passes AND the drift gate is clean, mark the phase done in the plan: `Edit` the `## Phase Status` section to flip `- [ ] Phase N: ...` → `- [x] Phase N: ...`. This single Edit is the durable record of progress — it survives `/clear` and lets in-session re-entry detect the next phase.
   - **Phase-boundary decision** — the phase is done; now decide stop vs. auto-advance, checking these in order (first match wins), then print the matching Phase-Complete Block:
     1. **Last phase** → STOP; print the completion footer (block C).
     2. **Phase 1**, any risk tier → STOP for **calibration** (block B). Cheapest place to catch the coder — and the plan's risk tagging — drifting from intent before phases 2..N build on it.
     3. **A gate needed an exception, a `/fix` loop hit its cap, or the coder flagged an ambiguity**, any tier → STOP (block B).
     4. **`(risk: high)`** — and an untagged phase counts as high → STOP for phase-level sign-off (block B).
     5. Otherwise — genuinely **`(risk: low)`** with all machine gates green → **AUTO-ADVANCE in-session** (block A): print the one-line advance notice, then re-enter step 2 for the next phase. Do NOT `/clear` and do NOT wait — subagent isolation keeps the main-loop context lean, so the coder's heavy context never lands here; the user can interrupt at any boundary.
   - If the plan has only one phase or no phase headers, treat it as a single dispatch (skip the phase loop).

3. **Determine scope**:
   - If a scope modifier (`be`, `fe`, `fs`) was provided, use that
   - Otherwise, analyze the task description — read referenced files, check relevant directories — and determine if this is frontend, backend, both, or neither (non-web repo: CLI tool, library, scripts, infra, config)

4. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Agent tool calls
   **Neither** (non-web repo) → Launch a single `coder` subagent — the frontend/backend split only applies to web-fullstack codebases

   For each coder:
   - Pass the full task description and any relevant context
   - Instruct it to follow existing patterns in the codebase
   - Write tests if needed
   - Flag any ambiguities or issues
   - If the task turns out to be architectural, have it report back and recommend `/eng-spec` instead

5. **After coder(s) complete**, summarize for the user AND build a handoff block for downstream review.

   User summary:
   - What was implemented
   - Any issues flagged
   - Any follow-up items

   Handoff block (passed as args to `/review` in step 5). Schema is defined in `review/SKILL.md` under "Handoff Block". Required fields:

   ```
   handoff:
     files:
       - path: <relative path>
         change: <one line: what changed and why>
     tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
     flagged: <issues the coder explicitly flagged, or "none">
     iter: 1
   ```

   The handoff lets the reviewer skip rediscovery — file scope, change intent, and test status are upstream context the reviewer no longer has to reconstruct via `git diff` and full re-reads. Coders already know all of this; pass it forward instead of forcing re-discovery.

6. **Auto-dispatch peer review**: After summarizing the coder output, tell the user: "Auto-dispatching `/review` to check the implementation before committing." Then invoke the `/review` skill via the Skill tool with `skill: "review"` and `args` containing the handoff block from step 5 plus any `+fast`/`+deep` modifier. This runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

7. **Multi-phase plans only — apply the phase-boundary decision**: If step 2 detected a multi-phase plan, after `/review` returns and the drift gate passes, run the **Phase-boundary decision** (step 2) to choose stop vs. auto-advance. On a STOP, print the matching phase-complete block with all placeholders resolved and wait; when the user confirms (in-session by default — `/clear` only if context genuinely got heavy), re-enter step 2 for the next phase, using the `## Phase Status` section (fallback: `git status` + success criteria) to detect what's already done. On an AUTO-ADVANCE, print the one-line advance notice and re-enter step 2 immediately for the next phase in the same context.

## Phase-Complete Block

After each phase + review + drift gate, the **Phase-boundary decision** (step 2) selects one of three blocks. Print the matching block verbatim with `<N>`, `<N+1>`, `<plan-path>`, and lists filled in.

**A — Auto-advance** (decision rule 5: genuinely `(risk: low)`, all machine gates green, not Phase 1, not the last phase, no exception/cap/ambiguity). No sign-off is requested; do not stop:

```
Phase <N> complete — machine gates green (review ✓, execution ✓, drift ✓, behavioral ✓). Risk: low. Manual verification: <n> agent-verified, <m> human-only deferred to the /q-verify packet.
→ Auto-advancing to Phase <N+1> in-session (no /clear; interrupt anytime).
```

Then re-enter step 2 for Phase <N+1> in the same context — do not wait for the user.

**B — Stop for sign-off** (decision rules 2–4: `(risk: high)` or untagged; OR Phase 1 calibration regardless of tier; OR any tier where a gate needed an exception, a fix loop hit its cap, or the coder flagged an ambiguity):

```
Phase <N> complete. Risk: <high | low — Phase 1 calibration | low — exception>. Phase-level sign-off requested.

Agent-verified (evidence in the plan):
- <item — one-line evidence summary>

Human-only verification remaining:
- <item 1>
- <...>

Next:
  1. Spot-check the evidence lines; run the human-only items.
  2. Confirm to continue to Phase <N+1> — in-session (no /clear needed; /clear only if context got heavy).

Or give feedback now for revisions to Phase <N>.
```

**C — Last phase** (decision rule 1): print block B's verification lists, then replace its "Next" block with:

```
All phases complete. Next: /q-verify (completeness + review packet; includes the remaining human-only checks) → /pr.
```

Resolution rules:

- `<N>` is the just-finished phase number; `<N+1>` the next.
- `<plan-path>` is the absolute or repo-relative path the orchestrator was invoked with.
- Verification items come from the just-finished phase's `#### Manual Verification:` section in the plan, split by the verifier agent's `agent-verified` / `human-only` tags. If that section is empty in block B, omit both lists and replace step 1 with: "Spot-check the diff."
- **No risk tag (older plan format) → treat as high** (block B).

For complex features requiring design decisions, use `/eng-spec` instead.

## Task

$ARGUMENTS
