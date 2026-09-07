---
name: todos
description: Recap the session's open work as a routable action list — one line per item, grouped by what the user does next. Use for "recap todos", "todos", "what's open", "where are we", "/todos". Session-scoped and conversational; NOT the branch closing phase (that is /branch-recap, which reads process residue and emits a handoff sheet).
allowed-tools: [Bash, Read, Grep, Glob]
---

# Todos

The user is deciding and routing, not reading. Output is a queue, not a report.

## Sources

The conversation, in priority order: deferred work, unstarted filed tickets, unfixed defects, session handoffs. Add `git status`/`git log --oneline -5` only when session state is stale or unclear.

Do NOT go looking — no scans, queries, or subagents. Unestablished-in-conversation means not a todo.

## Format

Group by ROUTE — what the user does with the item — not by topic or by ticket.

```
NOW
- <id> — <action, imperative, one line>. → <route>

BLOCKED
- <id> — <action>. waiting: <what>, <who owns it>

THEIRS
- <who> — <what they are doing>. lands: <what changes for us>
```

Rules:

- **One line each. No sub-bullets, no rationale, no evidence.**
- **Lead with the identifier** — ticket key, or `path:line`. It is what gets routed.
- **The action is a hand-off-able verb** — executable sight unseen.
- **`→ route`** names the lane: a skill (`/code`, `/eng-spec`, `/debug`, `/triage`),
  a person, or `drop`. Omit it only when genuinely unknown, and say so.
- **BLOCKED names event plus owner.** Ownerless means unstarted — put it in NOW.
- **Omit empty groups.**
- **Cap: 12 items.** Past that, list the top 12 and end with
  `+N more — ask to expand.`

## Closing line

One closing line only for time-sensitive or ordering-dependent items; else stop at the list.

Never append summaries, offers to start, or shipped-work recaps.

