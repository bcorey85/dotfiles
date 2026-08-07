---
name: cc
description: Read the inline code-review comments I left for you — from Neovim (`~/.claude/claude-comments.md` via `<leader>cc`) and from hunk review sessions (`prefix d`) — present them, answer the questions, hand the change requests to `/fix`, then clear them. Triggers on "I have comments for you", "claude comments", "I left you comments", "read my comments", "check claude-comments.md", "check hunk comments", "hunk review comments", "/cc".
allowed-tools: [Bash, Read, Glob, Grep, Skill]
---

# Read & Apply Claude Comments

The user authors inline comments in two readers — Neovim (`<leader>cc` → `:ClaudeReviewComment`, stored in `~/.claude/claude-comments.md`) and hunk (`prefix d`, built-in inline notes on `c`, mirrored per-checkout to `$XDG_STATE_HOME/hunk-claude/<slug>.comments.jsonl` by the `claude-review` extension). Both are explicit, user-written requests, the highest-priority kind of review feedback (not heuristic findings). This skill owns both lifecycles: it reads the in-scope entries from each, merges them into ONE queue, presents them, drives each to a terminal state, then clears the handled ones through whichever reader owns them.

One queue, one escape-log pass. The source only decides which script clears the entry.

**Not every comment asks for a diff.** A comment can be a question ("what is `monkeypatch`?", "why are we yielding here?") as legitimately as it can be a change request. Answering one IS handling it. `/fix` runs only for the entries that actually ask for a change, and a queue containing none is a complete, successful run — not an unhandled one.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md`; pass through to `/fix` unchanged. `+fast` when the comments are trivial (typos, simple style); `+deep` when a comment needs deep reasoning to address correctly.
- `+show` — read and present the comments, then **stop**. Do not hand off to `/fix` and do not resolve anything. Use when you just want to see what you flagged without acting on it. (The editor-side equivalent is `<leader>cp` in Neovim.)

## Instructions

1. **Parse modifiers** (`+fast` / `+deep` / `+show`). Strip them from the prompt; hold `+fast`/`+deep` to pass through to `/fix` in step 5.

2. **Resolve the repo root.** Run `git rev-parse --show-toplevel`. **If it fails (not inside a git repo)**, tell the user `/cc` must be run from within a git repo (comments are scoped per-repo) and stop. Hold the root for the script calls below.

3. **List in-scope entries from BOTH readers.** Use the bundled scripts for ALL reading — do NOT parse or rewrite `claude-comments.md` or hunk's JSONL by hand:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/claude-comments-consume" list "<repo-root>"
   bash "${CLAUDE_SKILL_DIR}/hunk-comments-consume" list "<repo-root>"
   ```

   Both return fresh (≤48h), current-repo entries as JSON with `id`, `path`, `line`, `timestamp`, `body`; hunk adds `side` and `hunk_index`. Entries from other repos are never listed or touched. Stale in-scope entries (>48h) are counted on stderr by each — sum them for the summary. Either script is a no-op returning `[]` when its reader has nothing (or is not installed).

   **Tag each entry with its source** (`nvim` or `hunk`) and keep that tag on it through step 6 — it is what routes the resolve. Merge the two lists into one queue ordered by `timestamp`.

   - **If the merged list is empty**, tell the user there are no fresh comments for this repo from either reader (mention the stale count if any) and stop. Do not invoke `/fix`.

4. **Present the entries and triage each one.** Group by file, show each `path:line` with its comment body and its source, so the user can see what is about to be acted on. **Record every entry `id` and source now** — you need this exact list for the mandatory resolve in step 6, and it must survive `/fix`'s (potentially long, multi-iteration) review loop.

   Sort every entry into exactly one bucket. Do this as you present, so the user can correct a misread before any coder spawns:

   | Bucket       | Test                                                                | Handled by                         |
   | ------------ | ------------------------------------------------------------------- | ---------------------------------- |
   | **change**   | asks for the code to be different                                   | `/fix` (step 5)                    |
   | **question** | asks you to explain existing code; a correct answer changes no file | answered in conversation (step 5a) |
   | **skip**     | false positive, intentional, or out of scope                        | nothing; note the reason           |
   | **defer**    | needs `/eng-spec`, or blocked on the user                           | nothing; stays queued              |

   When a comment does both ("why is this a dict — should be a list"), treat it as **change** and answer the question in the same reply. When it is genuinely ambiguous, ask — do not guess, and do not silently upgrade a question into a refactor.

   - **If `+show` was passed**, stop here. Do not answer, do not hand off to `/fix`, do not resolve.

5. **Hand off the `change` entries to `/fix`.** Skip this step entirely when the bucket is empty — an all-questions queue does not invoke `/fix`, and that is not a degraded run. Invoke the `/fix` skill via the Skill tool (`skill: "fix"`) with `args` containing:
   - The `change` entries as the issue source — each with `path`, `line`, `body`, and its `id`. Never pass a `question` entry to `/fix`; a coder handed a question will answer it with a diff.
   - A note that these are **user-authored review comments** (highest priority, not heuristic findings) so coders treat them as explicit requests, not optional suggestions. The source is bookkeeping — never pass it to `/fix` or let it rank the work.
   - Any `+fast` / `+deep` modifier parsed in step 1.

   `/fix` categorizes by owning coder, dispatches the coders in parallel, then auto-runs `/review`. Let it run its full pipeline.

5a. **Answer the `question` entries in conversation.** Answer each properly, at the depth the question asks for — where the thing comes from, what it does, why it is there. An answer that sends the user to read the docs themselves has not handled the comment. This is the whole handling for those entries; nothing is dispatched and no file changes.

Both step 5 and step 5a are conditional on their bucket being non-empty, and a run may legitimately do one, the other, both, or neither.

6. **Resolve handled entries — MANDATORY, do not skip.** Fire this when **every entry has reached a terminal state** — `change` fixed, `question` answered, `skip` triaged — **even if `/review` is still running or you've lost track of it**, and even if `/fix` never ran at all. Do NOT wait on a `/fix` handoff as the trigger: an all-questions queue never has one, and hanging the resolve off it is what caused runs to answer comments correctly and clear none of them, so the next run re-listed them as fresh.

   Treat this as a hard gate before you consider `/cc` done. Using the ids and sources recorded in step 4, call each script with ONLY its own source's ids:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/claude-comments-consume" resolve "<repo-root>" <nvim-id>...
   bash "${CLAUDE_SKILL_DIR}/hunk-comments-consume" resolve "<repo-root>" <hunk-id>...
   ```

   Skip a call entirely when that source has no ids. Pass the `id` of every entry that was **fixed**, **answered**, or **skipped after triage** (note skip reasons in the summary). Do **NOT** pass ids of **deferred** entries — they stay in the queue for next time.

   `answered` is a first-class terminal state, not a lesser one. A question you answered is as done as a bug you fixed; leaving it queued re-presents it to the user as if you had ignored it.

   Both are true resolves, and both re-read their store at resolve time so entries written since the list survive:
   - **nvim**: rewrites `claude-comments.md` without the resolved ids, deleting the file when nothing remains.
   - **hunk**: rewrites the mirrored JSONL without them, deleting the file when it empties. The note itself stays in hunk's own UI until cleared there, but nothing re-lists it — no by-hand step.

7. **Log escapes.** Every comment that resulted in a real fix is ground truth: the human caught something the automated gates blessed. For each entry **fixed** (not answered, not skipped-as-FP, not deferred), log one line. A run with no `change` entries logs nothing here, and that is correct — a question is not an escape, because no gate failed to catch anything.

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "<repo-root>")" stage_found=cc gate_missed=review class=<bug|smell|duplication|plan-drift|test-gap|other> severity=<high|medium|low> lane=<eng-spec|code|other> guard=<...> desc="<comment gist>" file=<path>
   ```

   `guard` is the ratchet rung from `~/.claude/skills/_shared/escape-ratchet.md` (batch by `class` across the resolved comments); surface the proposed guard in step 8's summary and apply it on approval.

   `stage_found=cc` for BOTH sources: same human-review stage, different reader. Splitting it would fragment the flywheel's per-gate rates across two buckets and make each look better than the gate is. Classify `class` from the comment body, and when unsure, `other`. `lane` is the planning lane that produced the work under comment — infer it from the conversation or the branch's planning artifacts (eng-spec doc → `eng-spec`, direct dispatch → `code`); ask the user only when genuinely ambiguous. Do NOT log comments that were new requirements or changed direction — a gate can't miss information it never had.

8. **Summarize** for the user: which comments were fixed, which were answered, which were skipped (with reasons), which were deferred and why, and the stale-dropped count (if any). State the resolve happened; a summary that lists outcomes without confirming the clear is how the previous failure went unnoticed.
