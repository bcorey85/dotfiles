# Phase 1: Ticket

1. **Get the ticket.** In order: a `/pull-ticket` result in the thread → use it;
   a ticket/spec file path in the argument → read it; a Jira key/URL (argument or
   branch) → **fetch it yourself** per `~/.claude/skills/_shared/jira-ticket.md`
   (read it). Required-ticket caller: no key → ask the user; Jira MCP down → say
   so and stop.

2. **Check for an existing spec** — Glob `docs/plans/**/spec.md`. If one
   matches, read it and ask: "Found an existing spec — update it or start fresh?"

3. **Open the task directory** `docs/plans/<slug>/`. **A Jira key always goes in
   the slug** (`RB-512`, `RB-512-invoice-export`). With no key, kebab-case the
   **area** touched plus the date, never the change (`invoice-export-0808`, not
   `fix-slow-invoice-export`). `Write` the ticket **verbatim** to
   `00-ticket.md` per the persistence rule in `jira-ticket.md`.
