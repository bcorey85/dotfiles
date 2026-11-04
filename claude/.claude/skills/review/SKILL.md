---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Code Review

## Instructions

**End the turn only at a STOP, a wait below, or the `launch` wait in step 1.** Everywhere else, take the next reversible step and report it afterward. Ask only before a step that cannot be undone or that leaves this machine, or when two paths are both defensible.

1. **Start the loop** in your first response. Run, as one Bash call with `run_in_background: true`:

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py launch [flags]
   ```

   Flags from `$ARGUMENTS`:
   - a `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`): Write it verbatim to a scratchpad file, then `--handoff <file>`; `--lane <lane>` when it names one
   - `base=<ref>`: `--base <ref>`
   - a file path, with no handoff block: `--file <path>`, once per file
   - `+fast`: `--fast`; `+deep`: `--deep`; `iter=N`: `--iter N`
   - `--repo <absolute path>` when the work lives outside your cwd's repo

   End the turn; when the command's completion notice arrives, read its output. If it printed `ACTION: stop-usage` (a clean tree), skip step 2: show the user its lines, never report a clean review.

   On `ACTION: dispatch-reviewer`: in one message, dispatch one `Agent` per listed line, `subagent_type` its agent, `model` only when the line names one, prompt `Read <prompt file> whole and do that task.` When they return, Write each one's final text verbatim to its report file. Then run the printed `wait` command with `run_in_background: true`, end the turn, and handle its output the same way. Dispatch no other agent.

2. **Run the packet command** that the last output printed once the loop finished or exited. If it stops with a saved-packet error (no dispatch on record), tell the user.

3. **Run the script and do what its `ACTION:` lines say.** Two duties are yours: judge the user's answer to each ask, then run the asks-done line the script printed; and on `show-plan-impacts` or `redispatch`, add the printed deviation lines under `## Plan Deviations` in the plan.

## Arguments

$ARGUMENTS
