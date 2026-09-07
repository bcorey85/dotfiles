---
name: create-ticket
description: Create a Jira ticket from intent + codebase scoping. Scopes the work against the real repo and writes a TIGHT description. Use when asked to "spec out a ticket", "make a ticket", "create a ticket".
allowed-tools:
  [
    Bash,
    Read,
    Glob,
    Grep,
    mcp__jira__createJiraIssue,
    mcp__jira__editJiraIssue,
    mcp__jira__getJiraIssue,
    mcp__jira__getJiraProjectIssueTypesMetadata,
    mcp__jira__getAccessibleAtlassianResources,
    mcp__jira__searchJiraIssuesUsingJql,
  ]
---

# Create a Jira Ticket

Turn a request (+ the current repo) into one well-scoped Jira ticket.

## Brevity contract — NON-NEGOTIABLE

The whole point of this skill. A ticket is a pointer to work, not a design doc.

- **Hard cap: the description fits on one screen (~150 words / ~15 lines).** If it doesn't, cut — don't scroll.
- **Bullets, not paragraphs. One line per bullet.** No multi-sentence bullets, no sub-bullets unless truly needed.
- **Definitions are terse:** name the thing, `path:line`, move on. No tool explanations, no domain teaching.
- **Say each thing once.** Don't repeat a point across Why / Scope / Acceptance.
- **Acceptance bullets are testable:** observable outcomes (command, behavior, dead repro) — "works correctly" doesn't qualify. Can't write the check → the ticket isn't clear; fix the ticket.
- **Why = 1–3 bullets max.** If the motivation needs a paragraph, it's a doc, not a ticket.
- **Default sections: just `## Work` and `## Acceptance`.** Add `## Why` only if non-obvious, `## Out of scope` only to head off scope creep, `## Open Questions` whenever the work is gated on an unanswered question (see below).
- **Link, don't transcribe** — reference files/PRs, never paste.

If you catch yourself writing prose to sound thorough in the main body: stop, delete it, move it to Technical Notes or cut it.

### Brevity ≠ deletion — never drop load-bearing specifics

The contract kills _padding_, not _content_. Some things are terse AND essential; they stay in the body, never cut, never buried in Technical Notes:

- **Open questions / blocking dependencies** → `## Open Questions` in the body. Anything awaiting a named owner or gating dependency — action items, not discovery; preserve every one with its owner.
- **Load-bearing examples** → keep in the body. A sample that _pins_ the requirement (input/output, payload, canonical query) is definition, not verbosity — reproduce faithfully. Skippable illustrations → Technical Notes.
- **Verbatim stakeholder asks** → exact quote + attribution. Never reword or drop (park long ones in Technical Notes).

Litmus test before cutting a line: _is this padding, or is it a specific the implementer/reviewer can't reconstruct?_ Padding goes. Specifics relocate at most — they never disappear.

### The verbosity escape valve: `## Technical Notes`

Discovery, file detail, gotchas, rejected approaches, the long "why" → **`## Technical Notes`** at the **very bottom** under a `---`. The ONE place verbosity is allowed.

- The contract above governs everything **above** the `---`. Technical Notes is below it.
- Omit the section entirely when there's nothing worth logging — don't pad it.
- The reader must be able to grasp the ticket from Work + Acceptance alone, ignoring Technical Notes.

## Steps

If the Jira MCP tools aren't available in this session, say so and stop — offer to draft the ticket text inline for manual filing instead.

### 1. Resolve the target

From the user's input figure out: project key, issue type, and parent (if any).

- **Jira URL/key given** (`https://<site>.atlassian.net/browse/ABC-123` or `ABC-123`) — usually the **parent epic** or context; confirm with getJiraIssue before assuming.
- **Cloud ID:** pass the site hostname (e.g. `<site>.atlassian.net`) straight to the jira tools as `cloudId`. Only if that fails, call `getAccessibleAtlassianResources`.
- **Issue type:** default **Task**. Use `getJiraProjectIssueTypesMetadata` if unsure which types exist. File under an epic via the `parent` field.
- If you'd be **overwriting** an existing ticket's description, stop and confirm — don't clobber.

### 2. Scope against the repo

Explore the codebase (Glob/Grep/Read) so the ticket names real files. Research is for _you_ — informs bullets, never lands in the description.

**Size check:** if scoping reveals the work can't plausibly land in a few days, flag it and confirm before filing. Don't refuse; the call is the user's.

### 3. Write it (honor the brevity contract)

- **Summary:** imperative, specific, no ticket-key prefix (Jira adds it).
- **Description:** plain markdown (MCP converts to ADF — never ADF JSON). Tight body + optional `---` + `## Technical Notes`.
- Surface genuine forks/risks as a single line in the body; the supporting detail goes in Technical Notes.

### 4. Create + report

- `createJiraIssue` (set `parent` for epic children).
- Report the new key + URL and a one-line summary of what you filed. Don't paste the whole description back.

## Arguments

$ARGUMENTS
