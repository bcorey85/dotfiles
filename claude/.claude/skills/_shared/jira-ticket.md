# Jira Ticket Resolution + Fetch

Canonical mechanics for locating and fetching a Jira ticket. Skills reference this file instead of redefining them (`/pull-ticket`, `/eng-spec` Phase 1, `/peer-review`); each caller's own section adds only what it does with the ticket and whether a ticket is required or optional.

## Resolve the key

Match `[A-Z][A-Z0-9]+-[0-9]+` against, in order (first hit wins):

1. An explicit key or Jira URL in the caller's arguments
2. The relevant branch name — current branch (`git branch --show-current`) or, for PR-scoped callers, the PR's head branch
3. Caller-supplied text (PR title, PR body, commit subjects)

No match → **required-ticket callers** ask the user which ticket; **optional-ticket callers** note "no ticket reference found" and continue without.

## Fetch

Use `getJiraIssue`. Resolve the Cloud ID portably: pass the Jira site hostname (e.g. `<site>.atlassian.net`) as `cloudId` if it's known from context (a ticket URL, project docs); otherwise call `getAccessibleAtlassianResources` first. Pull:

- Summary, description, acceptance criteria
- Current status
- Comments with context

If the Jira MCP tools aren't available in this session: **never guess or reconstruct ticket content.** Required-ticket callers say so and stop; optional-ticket callers note the gap and continue.

## Persisting to disk (callers that write the ticket to a file)

Write **raw fields only, verbatim** — no paraphrase, no summary, no goal words of your own. This matters most for contamination-sensitive pipelines (`/eng-spec` writes to `docs/eng-specs/<slug>/00-ticket.md` before the goal-blind research phase), but verbatim is the rule for every caller: a persisted ticket is a source document, not your reading of it.
