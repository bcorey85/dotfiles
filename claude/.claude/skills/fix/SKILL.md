---
name: fix
description: Dispatch coder subagents to fix review feedback (from a `/cc` comment handoff, a `/review` handoff, or the conversation), then auto-run `/review`. To act on inline comments left in `~/.claude/claude-comments.md`, use `/cc` — it reads them and routes here.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Fix Code Review Feedback

## Instructions

1. **Dispatch the loop** in your first response. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"`. Pass, verbatim:
   - `mode: fix-first`, `caller: fix`
   - `lane: <lane>` when the args name one (`lane: test-audit` from a test audit); else none
   - the findings, from whichever source applies: `/cc` entries (`path`, `line`, `body`, `id` — highest priority, user-authored), a `/review` handoff block, or the conversation
   - any `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`), `iter=N`, and any `+fast` / `+deep` modifier
   - `no-review` if present — the agent then verifies via the execution gate and returns without a reviewer pass
   - `repo: <absolute path>` when the work lives outside your cwd's repo (a sibling worktree)

   Invoked bare, with no findings in args and no handoff: if `~/.claude/claude-comments.md` may hold inline comments, point the user at `/cc` rather than parsing that file here.

2. **Run the script on the returned packet.** Decide the flags before you run it.

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py packet --skill fix --source <conversation|cc|handoff> [--lane <eng-spec|code|test-audit|other>] \
     [--escape "file=<path>|class=<class>|severity=<high|medium|low>|gate_missed=<review|drift-gate|test-intent|stage|coder|eng-spec>|guard=<type|convention|gotcha|rule|check|none|n-a>|desc=<one line>"]... \
     [--aikido "<path>:<line>=<comment_id>"]...
   ```

   - `--escape`, one per distinct defect: only when the user reported it in conversation, on code a prior `/review` on this branch already passed, and it is a defect, not a new requirement or a change of direction. Pick `guard` from `~/.claude/skills/_shared/escape-ratchet.md` without pausing. `lane` is `eng-spec` for an eng-spec doc, else `code`. When the user reports the defect after the packet ran, log it later with `python3 ~/.claude/scripts/review/review_fix.py escape --escape "..."`; the script records what it logged, so a repeat logs nothing twice.
   - `--aikido`, one per finding that is an Aikido PR comment (`author` is `aikido-pr-checks[bot]`, or the body carries `@AikidoSec` / `app.aikido.dev`, and it has a `comment_id`).

3. **Run the script and do what its `ACTION:` lines say.** Your duties: judge the user's answer to each ask, then run the asks-done line the script printed; on `show-plan-impacts` or `redispatch`, add the printed deviation lines under `## Plan Deviations` in the plan; state a proposed escape guard in your closing line and apply it on approval.

## Arguments

$ARGUMENTS
