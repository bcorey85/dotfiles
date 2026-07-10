---
name: fix
description: Dispatch coder subagents to fix review feedback (from a `/cc` comment handoff, a `/review` handoff, or the conversation), then auto-run `/review`. To act on inline comments left in `~/.claude/claude-comments.md`, use `/cc` — it reads them and routes here.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Fix Code Review Feedback

Thin wrapper. Fixing and the verification loop both live in the `review-loop`
agent (`~/.claude/agents/review-loop.md`), dispatched with `mode: fix-first`.
Your job is to hand it the findings, then render the packet it returns and
raise the modals it cannot.

## Modifiers

- `+fast` / `+deep` — semantics in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). Pass through verbatim; the agent maps them to the coder variant and model.

## Instructions

1. **Dispatch the loop**. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"` (the agent is unpinned). Pass, verbatim:
   - `mode: fix-first`, `caller: fix`
   - the findings, from whichever source applies: `/cc` entries (`path`, `line`, `body`, `id` — highest priority, user-authored), a `/review` handoff block, or the conversation
   - any `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`), `iter=N`, and any `+fast` / `+deep` modifier
   - `no-review` if present — the agent then verifies via the execution gate and returns without a reviewer pass

   Invoked bare, with no findings in args and no handoff: if `~/.claude/claude-comments.md` may hold inline comments, point the user at `/cc` rather than parsing that file here. `/cc` owns reading and clearing it.

2. **Route on the returned `status`** — first match wins:

   - **`plan-impact`** → raise the modal (see `/review`'s "Plan-impact findings" section — same routing), then re-dispatch with the decision and the returned `iter` preserved.
   - **`critical-blocker`** → STOP. Present `blockers` and wait. Do NOT re-dispatch.
   - **`cap-reached`** → STOP. Report `findings_remaining`; the user decides. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`converged`** → render the packet (step 3).

3. **Render the packet**: `### Findings by severity` from `fixed[]`; any issues the agent skipped, with its reasons; `medium.fix` applied and `medium.skip` with reasons; `perf[]` under its own heading with `Principle:` lines; `low[]` and notes inline. If any finding needs architectural rethinking, recommend `/eng-spec`.

4. **Raise what the agent could not**. Present `medium.ask` and `test_intent.ask`; wait for direction. Never auto-fix either.

## Arguments

$ARGUMENTS
