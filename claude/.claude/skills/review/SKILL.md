---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill. When it hands back, run `python3 ~/.claude/scripts/code/code_relay.py` in the same directory and do what it prints. When the user replies to a stop, run the stop's `To go on:` line with their reply as its feedback.
context: fork
agent: code-fork
model: sonnet
allowed-tools: [Agent, Bash, Read]
---

# Code Review

## Instructions

Read `~/.claude/skills/_shared/review-fork-run.md` whole first and follow it. **End the run only at a STOP or at the end of the run.**

1. **Start the loop**, unless the task text starts with `resume`:

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py launch --detach [flags]
   ```

   Flags from `$ARGUMENTS`:
   - a `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`): write it verbatim to `<run folder>/review-handoff.txt`, then `--handoff <that file>`; `--lane <lane>` when it names one
   - `base=<ref>`: `--base <ref>`
   - a file path, with no handoff block: `--file <path>`, once per file
   - `+fast`: `--fast`; `+deep`: `--deep`; `iter=N`: `--iter N`
   - `--repo <absolute path>` when the work lives outside your cwd's repo

   If it printed `ACTION: stop-usage` (a clean tree), end the run with its lines; never report a clean review.

2. **Run the packet command** the wait printed. If it stops with a saved-packet error (no dispatch on record), end the run with it.

3. **Do what its `ACTION:` lines say.**

## Arguments

$ARGUMENTS
