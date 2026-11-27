# Acceptance Criteria — comment-last-resort

criteria owner: user

> From the queue item's Done when. The user ruled the design; a session ruling moved the rule's home (D1 in `03-decisions.md`).

- **AC1** — The comment rule replaces the old "earns its place" guidance, reworded and never quoted: comments are a last resort, written only for what a busy engineer new to the code must know, and architecture goes in the repo's architecture docs, never in code comments.
  - The rule lives in `skills/coder-core/SKILL.md`; `_shared/code-vocabulary.md` keeps a one-line pointer to it (D1).
- **AC2** — Rule-meter on and off arms ran with the rule in the file that ships, with counts in the change file (kind user-rule, asked 2026-11-27).
- **AC3** — The comment gate keeps its four kept kinds and also passes a comment block of at most 2 added lines.
- **AC4** — A non-kept block of 3 or more lines is still blocked, and its message says architecture goes in the repo's architecture docs.
- **AC5** — A test pins 1, 2 and 3 line blocks.
- **AC6** — code-reviewer flags each added short comment a busy engineer new to the code would not need, with delete as the fix. Rule-meter arms ran for it in its own scenario.
- **AC7** — The gate applies in every repo. Nothing is written into any team repo.
- **AC8** — The old "earns its place" guidance is deleted.
- **AC9** — The rule-anchors rows for the changed sections are updated and `rule-anchors.sh check` passes.
