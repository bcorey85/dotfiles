---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Code Review

Thin wrapper over the `review-loop` agent. A script parses the returned packet, routes on status, renders it and logs the rows. You dispatch, run the script, and do what its `ACTION:` lines say.

## Modifiers

- `+fast` / `+deep` — pass through to the agent verbatim (semantics in `~/.claude/skills/_shared/modifiers.md`; read it only if you are unsure).

## Instructions

**End the turn only at a STOP or a wait below.** Everywhere else, take the next reversible step and report it afterward. Ask only before a step that cannot be undone or that leaves this machine, or when two paths are both defensible.

1. **Dispatch the loop** in your first response. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"`. Pass, verbatim:
   - `mode: review-first`, `caller: review`
   - any `handoff:` block from `$ARGUMENTS` (schema: `~/.claude/skills/_shared/handoff-block.md`)
   - any `+fast` / `+deep` modifier and `iter=N`
   - if `$ARGUMENTS` names a file path and no handoff block was given, scope the review to that file only
   - `base: <ref>` when `$ARGUMENTS` holds `base=<ref>`: the loop then reviews every change since that ref, commits included

2. **Run the script on the returned packet.** The script reads the packet a hook saved, for this session, when the loop handed back. Do not paste it. Running it again repeats no side effect:

   ```bash
   python3 ~/.claude/scripts/review-fix.py packet --skill review [--scope branch-exit] [--lane <eng-spec|code|other>]
   ```

   If it stops with a saved-packet error (no dispatch on record), run `~/.claude/scripts/review-gate-mark dirty` if you marked, and tell the user.

   `--scope branch-exit` when you dispatched with `base=`. `--lane` only when the handoff names one.

   When the packet's first line is `status: converged` or `status: deferred`, put `~/.claude/scripts/review-gate-mark clean` in the same response as a second, parallel Bash call. For any other status, never mark. If the gate denies a `clean` mark, leave the gate dirty, tell the user the reason it gave, and do not retry the mark.

3. **Do what the script printed.** Read the `ACTION:` line:

   - `render-and-finish` → say the text between `BEGIN USER TEXT` and `END USER TEXT` verbatim, then your one closing line. If the gate mark did not run in parallel, run it now as its own Bash command.
   - `present-asks` → say the user text, then present each ask with its question and wait. The script already ran nvim-jump. Never auto-fix an ask. After the answers run `python3 ~/.claude/scripts/review-fix.py asks-done <accepted|rejected|modified>[:<note>] ...`, one outcome per ask in order.
   - `ask-user-plan-impact` → call `AskUserQuestion` as printed, then run the `decide` command it names. On `ACTION: redispatch`, re-dispatch `review-loop` with the same arguments plus the lines it printed (both counters kept), then run step 2 again. On `ACTION: discuss`, talk it through with the user, then run the `decide` command that it printed for the outcome.
   - `stop` → present what it printed, wait for direction. Do NOT re-dispatch, do NOT `/fix`, do NOT mark.
   - `stop-no-handback` → the loop ended without handing back. Do what the lines say: the first time, re-dispatch `review-loop` once with the same arguments and run step 2 again; the second time, stop and show the user the loop's final text. Never mark clean.
   - `stop-parse-failure` or `stop-usage` → the packet or the call was bad. If you ran the gate mark in parallel, run `~/.claude/scripts/review-gate-mark dirty`. Show the user the problems. Never guess a missing field.

4. **What stays yours:** judging the user's answer to an ask, acting on accepted asks, and the closing line. The script's `MODEL STILL DOES:` line lists the rest.

## Arguments

$ARGUMENTS
