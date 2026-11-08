---
name: fix
description: Dispatch coder subagents to fix review feedback (from a `/cc` comment handoff, a `/review` handoff, or the conversation), then auto-run `/review`. To act on inline comments left in `~/.claude/claude-comments.md`, use `/cc` — it reads them and routes here. When it hands back, run `python3 ~/.claude/scripts/code/code_relay.py` in the same directory and do what it prints. When the user replies to a stop, run the stop's `To go on:` line with their reply as its feedback.
context: fork
agent: code-fork
model: sonnet
allowed-tools: [Agent, Bash, Read]
---

# Fix Code Review Feedback

## Instructions

Read `~/.claude/skills/_shared/review-fork-run.md` whole first and follow it. **End the run only at a STOP or at the end of the run.**

1. **Start the loop**, unless the task text starts with `resume`. Write the findings to `<run folder>/fix-findings.md`, one per item: `- <path>:<line> <finding>` at column 0, continuation lines indented. Take them from whichever source applies: `/cc` entries (`path`, `line`, `body`, `id` — highest priority, user-authored), a `/review` handoff block, or the conversation. Then run:

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py launch --detach --fix <run folder>/fix-findings.md [flags]
   ```

   Flags from the args:
   - `--lane <lane>` when the args name one (`test-audit` from a test audit); else `--lane eng-spec` for an eng-spec doc
   - a `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`): write it verbatim to `<run folder>/review-handoff.txt`, then `--handoff <that file>`
   - `no-review`: `--no-review`; `+fast`: `--fast`; `+deep`: `--deep`; `iter=N`: `--iter N`
   - `--repo <absolute path>` when the work lives outside your cwd's repo

   Invoked bare, with no findings in args and no handoff: if `~/.claude/claude-comments.md` may hold inline comments, end the run pointing the user at `/cc` rather than parsing that file here.

2. **Run the packet command** the wait printed, with these flags added. Decide them before you run it.

   ```bash
   <printed packet command> --source <conversation|cc|handoff> \
     [--escape "file=<path>|class=<class>|severity=<high|medium|low>|gate_missed=<review|drift-gate|test-intent|stage|coder|eng-spec>|guard=<type|convention|gotcha|rule|check|none|n-a>|desc=<one line>"]... \
     [--aikido "<path>:<line>=<comment_id>"]... [--pr <number>]
   ```

   - `--escape`, one per distinct defect: only when the user reported it in conversation, on code a prior `/review` on this branch already passed, and it is a defect, not a new requirement or a change of direction. Pick `guard` from `~/.claude/skills/_shared/escape-ratchet.md` without pausing. When the user reports the defect after the packet ran, log it later with `python3 ~/.claude/scripts/review/review_fix.py escape --escape "..."`; the script records what it logged, so a repeat logs nothing twice.
   - `--aikido`, one per finding that is an Aikido PR comment (`author` is `aikido-pr-checks[bot]`, or the body carries `@AikidoSec` / `app.aikido.dev`, and it has a `comment_id`). With them, `--pr` with the PR number the findings came with.

3. **Do what its `ACTION:` lines say.** State a proposed escape guard in your closing line; on resume, a coder applies it when the user approves.

## Arguments

$ARGUMENTS
