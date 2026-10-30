---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Code Review

Thin wrapper over the review loop: the scripted loop for a working-tree review, the `review-loop` agent for the rest. A script parses the returned packet, routes on status, renders it and logs the rows. You dispatch, run the script, and do what its `ACTION:` lines say.

## Modifiers

- `+fast` / `+deep` — pass through to the agent verbatim (semantics in `~/.claude/skills/_shared/modifiers.md`; read it only if you are unsure).

## Instructions

**End the turn only at a STOP, a wait below, or the `launch` wait in step 1.** Everywhere else, take the next reversible step and report it afterward. Ask only before a step that cannot be undone or that leaves this machine, or when two paths are both defensible.

1. **Start the loop** in your first response.

   **Script** when `$ARGUMENTS` holds no `handoff:` block, no `base=`, no file path, no `+fast` / `+deep` and no `iter=`. Run, as one Bash call with `run_in_background: true`:

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py launch [--repo <absolute path>]
   ```

   `--repo` when the work lives outside your cwd's repo. End the turn; when the command's completion notice arrives, run step 2. Do not dispatch an agent.

   **Agent** otherwise. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"`. Pass, verbatim:
   - `mode: review-first`, `caller: review`
   - any `handoff:` block from `$ARGUMENTS` (schema: `~/.claude/skills/_shared/handoff-block.md`)
   - any `+fast` / `+deep` modifier and `iter=N`
   - if `$ARGUMENTS` names a file path and no handoff block was given, scope the review to that file only
   - `base: <ref>` when `$ARGUMENTS` holds `base=<ref>`: the loop then reviews every change since that ref, commits included
   - `repo: <absolute path>` when the work lives outside your cwd's repo (a sibling worktree)

2. **Run the script on the returned packet.** The script reads the packet saved for this session when the loop handed back: the loop script stores it itself, and a hook stores it for a dispatched agent. Do not paste it. Running it again repeats no side effect:

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py packet --skill review [--scope branch-exit] [--lane <eng-spec|code|other>]
   ```

   If it stops with a saved-packet error (no dispatch on record), run `~/.claude/scripts/review/review-gate-mark dirty` if you marked, and tell the user.

   `--scope branch-exit` when you dispatched with `base=`. `--lane` only when the handoff names one.

   When the packet's `status` is `converged` or `deferred`, put `~/.claude/scripts/review/review-gate-mark clean` in the same response as a second, parallel Bash call. For any other status, never mark. If the gate denies a `clean` mark, leave the gate dirty, tell the user the reason it gave, and do not retry the mark.

3. **Do what the script printed.** Read the `ACTION:` line:

   - `render-and-finish` → say the text between `BEGIN USER TEXT` and `END USER TEXT` verbatim, then your one closing line. If the gate mark did not run in parallel, run it now as its own Bash command.
   - `present-asks` → say the user text, then present each ask with its question and its proposed change, and wait. The script already ran nvim-jump. Never auto-fix an ask. After the answers run `python3 ~/.claude/scripts/review/review_fix.py asks-done <accepted|rejected|modified>[:<note>] ...` (the note is accepted and not stored), one outcome per ask in order. When the repo's CLAUDE.md hands ask decisions to the session, decide each ask yourself and add `--by session`. When the script's asks-done line names `--packet <packet_id>`, run it as printed. The script supplies each ask's `finding_id` (the id of the loop's logged ask row); an ask it cannot match is logged under a new id.
   - `ask-user-plan-impact` → call `AskUserQuestion` as printed (without that tool, ask it in plain text with the options numbered and wait), then run the `decide` command it names. On `ACTION: redispatch`, re-dispatch `review-loop` with the same arguments plus the lines it printed (both counters kept), then run step 2 again. On `ACTION: discuss`, talk it through with the user, then run the `decide` command that it printed for the outcome.
   - `redispatch` → a plan impact that changes no acceptance criterion was adopted by rule. Show the user the printed deviation line and ask nothing. Add the printed lines under `## Plan Deviations` in the plan, re-dispatch `review-loop` with the same arguments plus the lines it printed (both counters kept), then run step 2 again.
   - `stop` → present what it printed, wait for direction. When it lists asks, run its printed asks-done line after the user answers. Do NOT re-dispatch, do NOT `/fix`, do NOT mark.
   - `stop-no-handback` → the loop ended without handing back. Do what the lines say: the first time, run `launch` again after a script start, else re-dispatch `review-loop` once with the same arguments, and run step 2 again; the second time, stop and show the user the loop's final text. Never mark clean.
   - `stop-no-reviewer` → the first time, re-dispatch `review-loop` once with the same arguments, the printed `iter=` line in place of any `iter=` line, and run step 2 again; the second time, stop and tell the user no reviewer ran. Never mark clean.
   - `wait-for-loop` → the loop is waiting on an agent or shell it started in the background. Do not re-dispatch and never mark clean. End the turn; when the review-loop's completion notice arrives, run step 2 again.
   - `stop-parse-failure` or `stop-usage` → the packet or the call was bad. If you ran the gate mark in parallel, run `~/.claude/scripts/review/review-gate-mark dirty`. Show the user the problems. Never guess a missing field.

   After a plan-impact ruling, and for the `redispatch` and `stop-no-reviewer` statuses, re-dispatch the `review-loop` agent with the printed lines (deviation lines, an `iter=` line), which the script never reads.

4. **What stays yours:** judging the user's answer to an ask, acting on accepted asks, and the closing line. The script's `MODEL STILL DOES:` line lists the rest.

## Arguments

$ARGUMENTS
