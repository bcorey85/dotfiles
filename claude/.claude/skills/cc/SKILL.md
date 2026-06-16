---
name: cc
description: Read the inline code-review comments I left for you in `~/.claude/claude-comments.md` (written from Neovim via `<leader>cc` / `:ClaudeReviewComment`), present them, then hand them to `/fix` to resolve. Triggers on "I have comments for you", "claude comments", "I left you comments", "read my comments", "check claude-comments.md", "/cc".
allowed-tools: [Bash, Read, Glob, Grep, Skill]
---

# Read & Apply Claude Comments

`~/.claude/claude-comments.md` holds inline comments the user authored in Neovim (`<leader>cc` → `:ClaudeReviewComment`) — explicit, user-written requests, the highest-priority kind of review feedback (not heuristic findings). This skill owns that file's lifecycle: it reads the in-scope entries, presents them, hands them to `/fix` for the actual coder dispatch + verification loop, then clears the ones that were handled.

## Modifiers

- `+fast` — pass through to `/fix` (→ `model: "haiku"` coders). Use when the comments are trivial (typos, simple style).
- `+deep` — pass through to `/fix` (→ `-deep` Opus coders). Use when a comment needs deep reasoning to address correctly.
- `+show` — read and present the comments, then **stop**. Do not hand off to `/fix` and do not resolve anything. Use when you just want to see what you flagged without acting on it. (The editor-side equivalent is `<leader>cp` in Neovim.)

## Instructions

1. **Parse modifiers** (`+fast` / `+deep` / `+show`). Strip them from the prompt; hold `+fast`/`+deep` to pass through to `/fix` in step 4.

2. **Resolve the repo root.** Run `git rev-parse --show-toplevel`. **If it fails (not inside a git repo)**, tell the user `/cc` must be run from within a git repo (comments are scoped per-repo) and stop. Hold the root for the script calls below.

3. **List in-scope entries.** Use the bundled script for ALL reading — do NOT parse or rewrite `claude-comments.md` by hand:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/claude-comments-consume" list "<repo-root>"
   ```

   Returns fresh (≤48h), current-repo entries as JSON (`[{id, path, line, timestamp, body}]`). Entries from other repos are never listed or touched. Stale in-scope entries (>48h) are counted on stderr — note that count for the summary.

   - **If the list is empty**, tell the user there are no fresh comments in `~/.claude/claude-comments.md` for this repo (mention the stale count if any) and stop. Do not invoke `/fix`.

4. **Present the entries** to the user — group by file, show each `path:line` with its comment body, so they can see what's about to be acted on. **Record every entry `id` now** — you will need this exact list for the mandatory resolve in step 6, and it must survive `/fix`'s (potentially long, multi-iteration) review loop.

   - **If `+show` was passed**, stop here. Do not hand off to `/fix`; do not resolve.

5. **Hand off to `/fix`.** Invoke the `/fix` skill via the Skill tool (`skill: "fix"`) with `args` containing:
   - The full entry list as the issue source — each with `path`, `line`, `body`, and its `id`.
   - A note that these are **user-authored `claude-comments.md` comments** (highest priority, not heuristic findings) so coders treat them as explicit requests, not optional suggestions.
   - Any `+fast` / `+deep` modifier parsed in step 1.

   `/fix` categorizes by owning coder, dispatches the coders in parallel, then auto-runs `/review`. Let it run its full pipeline.

6. **Resolve handled entries — MANDATORY, do not skip.** The moment `/fix`'s coders have applied their fixes, clear the handled comments — **even if the `/review` loop is still running or you've lost track of it**. This is the easiest step to forget after a long review loop; treat it as a hard gate before you consider `/cc` done. Using the ids recorded in step 4:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/claude-comments-consume" resolve "<repo-root>" <id>...
   ```

   Pass the `id` of every entry that was **resolved** (fix applied) or **skipped after triage** (false positive, intentional, out of scope — note skip reasons in the summary). Do **NOT** pass ids of **deferred** entries (recommended `/eng-spec`, waiting on user input) — they stay in the file for next time. The script re-reads the file at resolve time, so comments added by another nvim session in the meantime are preserved; it deletes the file when nothing remains.

7. **Summarize** for the user: which comments were fixed, which were skipped (with reasons), which were deferred and why, and the stale-dropped count (if any).
