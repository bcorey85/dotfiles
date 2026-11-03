---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Code Review

## Instructions

**End the turn only at a STOP, a wait below, or the `launch` wait in step 1.** Everywhere else, take the next reversible step and report it afterward. Ask only before a step that cannot be undone or that leaves this machine, or when two paths are both defensible.

1. **Start the loop** in your first response.

   **Script** when `$ARGUMENTS` holds no `handoff:` block, no `base=`, no file path, no `+fast` / `+deep` and no `iter=`. Run, as one Bash call with `run_in_background: true`:

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py launch [--repo <absolute path>]
   ```

   `--repo` when the work lives outside your cwd's repo. End the turn; when the command's completion notice arrives, read its output. If it printed `ACTION: stop-usage` (a clean tree), skip step 2: show the user its lines, never report a clean review.

   On `ACTION: dispatch-reviewer`: in one message, dispatch one `Agent` per listed line, `subagent_type` its agent, no `model`, prompt `Read <prompt file> whole and do that task.` When they return, Write each one's final text verbatim to its report file. Then run the printed `wait` command with `run_in_background: true`, end the turn, and handle its output the same way. Run step 2 once a line says the loop finished or exited. Dispatch no other agent.

   **Agent** otherwise. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"`. Pass, verbatim:
   - `mode: review-first`, `caller: review`
   - any `handoff:` block from `$ARGUMENTS` (schema: `~/.claude/skills/_shared/handoff-block.md`)
   - any `+fast` / `+deep` modifier and `iter=N`
   - if `$ARGUMENTS` names a file path and no handoff block was given, scope the review to that file only
   - `base: <ref>` when `$ARGUMENTS` holds `base=<ref>`: the loop then reviews every change since that ref, commits included
   - `repo: <absolute path>` when the work lives outside your cwd's repo (a sibling worktree)

2. **Run the script on the returned packet:**

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py packet --skill review [--scope branch-exit] [--lane <eng-spec|code|other>]
   ```

   If it stops with a saved-packet error (no dispatch on record), tell the user.

   `--scope branch-exit` when you dispatched with `base=`. `--lane` only when the handoff names one.

3. **Run the script and do what its `ACTION:` lines say.** Two duties are yours: judge the user's answer to each ask, then run the asks-done line the script printed; and on `show-plan-impacts` or `redispatch`, add the printed deviation lines under `## Plan Deviations` in the plan.

## Arguments

$ARGUMENTS
