---
name: todos
description: Recap the session's open work as a routable action list — one line per item, grouped by what the user does next. Use for "recap todos", "todos", "what's open", "where are we", "/todos". Session-scoped and conversational; NOT the branch closing phase (that is /branch-recap, which reads process residue and emits a handoff sheet).
allowed-tools: [Bash, Read, Grep, Glob]
---

# Todos

The user is deciding and routing, not reading. Output is a queue, not a report.

## Sources

The conversation, in priority order: work explicitly deferred, tickets filed but
unstarted, defects found and not fixed, handoffs to other sessions. Add `git status`
and `git log --oneline -5` only when the session's state is stale or unclear.

Do NOT go looking for work. No repo scans, no ticket queries, no subagents. If it
wasn't established in this conversation, it isn't a todo — this skill reports what
is already known, and costs one turn.

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

- **One line each. No sub-bullets, no rationale, no evidence.** The reasoning is
  already in the transcript; if the user wants it they will ask about that item.
- **Lead with the identifier** — ticket key, or `path:line`. It is what gets routed.
- **The action is a verb the user could hand to someone.** "Measure whether an
  activities date fans the view" routes; "investigate the activity_count situation"
  does not.
- **`→ route`** names the lane: a skill (`/code`, `/eng-spec`, `/debug`, `/triage`),
  a person, or `drop`. Omit it only when genuinely unknown, and say so.
- **BLOCKED names the unblocking event and its owner.** A blocked item with no owner
  is not blocked, it is unstarted — put it in NOW.
- **Omit empty groups.** Do not print a header to say nothing is under it.
- **Cap: 12 items.** Past that, list the top 12 and end with
  `+N more — ask to expand.` A list longer than a screen is not a decision aid.

## Closing line

One line, only if something is genuinely time-sensitive or ordering-dependent
(a blocker draining, a decision gating two items). Otherwise stop after the list.

Never append a summary, a status paragraph, an offer to start any of it, or a
recap of what shipped this session. Shipped work is not a todo.
