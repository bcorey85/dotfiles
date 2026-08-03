---
name: tuicr-cc
description: Read the review comments I left in tuicr (prefix d popup), present them, hand them to `/fix`, and log the escapes. The tuicr twin of `/cc`. Triggers on "check tuicr comments", "read my tuicr comments", "tuicr review comments", "/tuicr-cc".
allowed-tools: [Bash, Read, Glob, Grep, Skill]
---

# Read & Apply tuicr Comments

tuicr persists review comments per checkout under `~/.local/share/tuicr/reviews`. They are explicit, user-written requests — the same priority as `/cc` comments, not heuristic findings. This skill reads the in-scope ones, presents them, hands them to `/fix`, logs the escapes, and marks them consumed.

`/cc` and this skill are independent queues over the same review habit. Running one never touches the other's comments.

## Modifiers

- `+fast` / `+deep` — semantics in `~/.claude/skills/_shared/modifiers.md`; pass through to `/fix` unchanged.
- `+show` — read and present, then **stop**. No `/fix`, no escape logging, no consume.

## Consume is not resolve

tuicr exposes `review list`, `review add`, and `review comments` — no delete and no mark-resolved. A consumed comment therefore stays visible in the tuicr TUI; only the sidecar (`~/.claude/tuicr-consumed.txt`) knows it was handled, which is what stops a second run from double-logging the same escape. Tell the user which comments to clear in the TUI as part of the summary. If tuicr grows a real resolve, delete the sidecar and call it instead.

## Instructions

1. **Parse modifiers** (`+fast` / `+deep` / `+show`). Strip them; hold `+fast`/`+deep` for step 5.

2. **Resolve the repo root.** `git rev-parse --show-toplevel`. If it fails, tell the user this skill must run inside a git repo (tuicr sessions are per-checkout) and stop.

3. **List in-scope comments.** Use the bundled script for ALL reading — never parse tuicr's session JSON by hand:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/tuicr-comments-consume" list "<repo-root>"
   ```

   Returns un-consumed, fresh (≤48h) `local_draft` comments as JSON (`[{id, session, path, line, end_line, comment_type, timestamp, body}]`). Stale comments are counted on stderr — note that count for the summary.

   If the list is empty, say so (mention the stale count if any) and stop. Do not invoke `/fix`.

4. **Present the comments**, grouped by file, each as `path:line` with its body and `comment_type` when not `none`. **Record every `id` now** — step 6 and step 7 need this exact list, and it must survive `/fix`'s multi-iteration loop.

   If `+show` was passed, stop here.

5. **Hand off to `/fix`** via the Skill tool (`skill: "fix"`) with `args` containing each comment's `path`, `line`, `body`, and `id`; a note that these are **user-authored tuicr review comments** (highest priority, explicit requests, not optional suggestions); and any `+fast`/`+deep`.

6. **Log escapes — do this BEFORE the consume in step 7.** Every comment that produced a real fix is ground truth: the human caught what the automated gates blessed. For each comment **resolved with a fix applied** (not skipped-as-FP, not deferred):

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "<repo-root>")" stage_found=cc gate_missed=review class=<bug|smell|duplication|complexity|plan-drift|test-gap|other> severity=<high|medium|low> lane=<eng-spec|code|other> guard=<...> desc="<comment gist>" file=<path>
   ```

   `guard` is the ratchet rung from `~/.claude/skills/_shared/escape-ratchet.md` (batch by `class`); surface the proposed guard in step 8 and apply it on approval.

   `stage_found=cc` deliberately: this is the same human-review stage as `/cc`, on a different reader, and splitting it would fragment the flywheel's per-gate rates. Map `comment_type` to `class` when the comment is typed; otherwise classify from the body, `other` when unsure. Do NOT log comments that were new requirements or changed direction — a gate cannot miss information it never had.

7. **Mark consumed — MANDATORY.** Once `/fix`'s coders have applied their fixes, even if `/review` is still running:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/tuicr-comments-consume" resolve "<repo-root>" <id>...
   ```

   Pass the `id` of every comment **resolved** or **skipped after triage**. Do NOT pass **deferred** ids — they stay in the queue.

8. **Summarize**: fixed / skipped (with reasons) / deferred (with reasons), the stale-dropped count, and the list of `path:line` the user should clear in the tuicr TUI.
