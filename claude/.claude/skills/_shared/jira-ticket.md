# Jira Ticket Resolution + Fetch

Locating + fetching a Jira ticket. Referenced by `/pull-ticket`, `/eng-spec` Phase 1, `/peer-review`; callers add only their use + required/optional.

## Resolve the key

Match `[A-Z][A-Z0-9]+-[0-9]+` against, in order (first hit wins):

1. An explicit key or Jira URL in the caller's arguments
2. The relevant branch name — current branch (`git branch --show-current`) or, for PR-scoped callers, the PR's head branch
3. Caller-supplied text (PR title, PR body, commit subjects)

No match → **required-ticket callers** ask the user which ticket; **optional-ticket callers** note "no ticket reference found" and continue without.

## Fetch

Use `getJiraIssue`. Cloud ID: pass the site hostname as `cloudId` if known from context, else `getAccessibleAtlassianResources` first. Pull:

- Summary, description, acceptance criteria
- Current status
- Comments with context

No Jira MCP: **never guess ticket content.** Required callers stop; optional note the gap and continue.

## Persisting to disk (callers that write the ticket to a file)

Write **raw fields only, verbatim** — a persisted ticket is a source document, not your reading.