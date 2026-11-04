---
name: fix
description: Dispatch coder subagents to fix review feedback (from a `/cc` comment handoff, a `/review` handoff, or the conversation), then auto-run `/review`. To act on inline comments left in `~/.claude/claude-comments.md`, use `/cc` — it reads them and routes here.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Fix Code Review Feedback

## Instructions

1. **Start the loop** in your first response. Write the findings to a scratchpad file, one per item: `- <path>:<line> <finding>` at column 0, continuation lines indented. Take them from whichever source applies: `/cc` entries (`path`, `line`, `body`, `id` — highest priority, user-authored), a `/review` handoff block, or the conversation. Then run, as one Bash call with `run_in_background: true`:

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py launch --fix <findings file> [flags]
   ```

   Flags from the args:
   - `--lane <lane>` when the args name one (`test-audit` from a test audit); else `--lane eng-spec` for an eng-spec doc
   - a `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`): Write it verbatim to a scratchpad file, then `--handoff <file>`
   - `no-review`: `--no-review`; `+fast`: `--fast`; `+deep`: `--deep`; `iter=N`: `--iter N`
   - `--repo <absolute path>` when the work lives outside your cwd's repo

   Invoked bare, with no findings in args and no handoff: if `~/.claude/claude-comments.md` may hold inline comments, point the user at `/cc` rather than parsing that file here.

   End the turn; when the command's completion notice arrives, read its output. On `ACTION: dispatch-reviewer`: in one message, dispatch one `Agent` per listed line, `subagent_type` its agent, `model` only when the line names one, prompt `Read <prompt file> whole and do that task.` When they return, Write each one's final text verbatim to its report file. Then run the printed `wait` command with `run_in_background: true`, end the turn, and handle its output the same way. Dispatch no other agent.

2. **Run the packet command** that the last output printed once the loop finished or exited, with these flags added. Decide them before you run it.

   ```bash
   <printed packet command> --source <conversation|cc|handoff> \
     [--escape "file=<path>|class=<class>|severity=<high|medium|low>|gate_missed=<review|drift-gate|test-intent|stage|coder|eng-spec>|guard=<type|convention|gotcha|rule|check|none|n-a>|desc=<one line>"]... \
     [--aikido "<path>:<line>=<comment_id>"]...
   ```

   - `--escape`, one per distinct defect: only when the user reported it in conversation, on code a prior `/review` on this branch already passed, and it is a defect, not a new requirement or a change of direction. Pick `guard` from `~/.claude/skills/_shared/escape-ratchet.md` without pausing. When the user reports the defect after the packet ran, log it later with `python3 ~/.claude/scripts/review/review_fix.py escape --escape "..."`; the script records what it logged, so a repeat logs nothing twice.
   - `--aikido`, one per finding that is an Aikido PR comment (`author` is `aikido-pr-checks[bot]`, or the body carries `@AikidoSec` / `app.aikido.dev`, and it has a `comment_id`).

3. **Run the script and do what its `ACTION:` lines say.** Your duties: judge the user's answer to each ask, then run the asks-done line the script printed; on `show-plan-impacts` or `redispatch`, add the printed deviation lines under `## Plan Deviations` in the plan; state a proposed escape guard in your closing line and apply it on approval.

## Arguments

$ARGUMENTS
