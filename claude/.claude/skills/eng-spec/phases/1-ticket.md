# Phase 1: Ticket

1. **Get the ticket.** In order: a `/pull-ticket` result in the thread → use it;
   a ticket/spec file path in the argument → read it; a Jira key/URL (argument or
   branch) → **fetch it yourself** per `~/.claude/skills/_shared/jira-ticket.md`
   (read it). Required-ticket caller: no key → ask the user; Jira MCP down → say
   so and stop.

2. **If no context is apparent**, ask: "What are we building? Describe the
   feature or paste a ticket."

3. **Check for an existing spec** — Glob `docs/plans/**/spec.md`. If one
   matches, read it and ask: "Found an existing spec — update it or start fresh?"

4. **Open the task directory** `docs/plans/<slug>/` (Jira key, else
   kebab-case from the description) and `Write` the ticket **verbatim** to
   `00-ticket.md` per the persistence rule in `jira-ticket.md`. You are a
   courier: a paraphrased ticket has your reading already baked in.
