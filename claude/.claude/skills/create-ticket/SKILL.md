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
- **Definitions are terse.** Name the thing, point to the file (`path:line`), move on. Do NOT explain what a tool/config does, re-derive rationale, or teach the reader the domain.
- **Say each thing once.** Don't repeat a point across Why / Scope / Acceptance.
- **Why = 1–3 bullets max.** If the motivation needs a paragraph, it's a doc, not a ticket.
- **Default sections: just `## Work` and `## Acceptance`.** Add `## Why` only if non-obvious, `## Out of scope` only to head off scope creep, `## Open Questions` whenever the work is gated on an unanswered question (see below).
- **Link, don't transcribe.** Reference repo files/PRs instead of pasting their contents or summarizing them at length.

If you catch yourself writing prose to sound thorough in the main body: stop, delete it, move it to Technical Notes or cut it.

### Brevity ≠ deletion — never drop load-bearing specifics

The contract kills *padding*, not *content*. Some things are terse AND essential; they stay in the body, never cut, never buried in Technical Notes:

- **Open questions / blocking dependencies** → `## Open Questions` in the body. Anything awaiting an answer from a named person or team (e.g. "for Amik: which schema name is correct?"), or an external dependency that gates the work. These are action items, not discovery. Preserve every one; attribute who owns the answer.
- **Load-bearing examples** → keep in the body (a `## Example` block, or inline). A concrete sample that *pins* the requirement — a representative input/output, a sample payload, a canonical query — is part of the definition, not verbosity. Reproduce it faithfully (code fences intact). Only illustrative-but-skippable examples go to Technical Notes.
- **Verbatim stakeholder asks** → preserve the exact quote + attribution (who, when, where). Paraphrasing loses the source of truth; park the quote in Technical Notes if it's long, but never reword or drop it.

Litmus test before cutting a line: *is this padding, or is it a specific the implementer/reviewer can't reconstruct?* Padding goes. Specifics relocate at most — they never disappear.

### The verbosity escape valve: `## Technical Notes`

Discovery findings, file-by-file detail, gotchas, rejected approaches, the long "why" — they go in a **`## Technical Notes`** section at the **very bottom**, under a `---` rule that separates it from the problem definition. This is the ONE place verbosity is allowed.

- The contract above governs everything **above** the `---`. Technical Notes is below it.
- Omit the section entirely when there's nothing worth logging — don't pad it.
- The reader must be able to grasp the ticket from Work + Acceptance alone, ignoring Technical Notes.

## Steps

### 1. Resolve the target

From the user's input figure out: project key, issue type, and parent (if any).

- **Jira URL/key given** (`https://<site>.atlassian.net/browse/ABC-123` or `ABC-123`) — that's usually the **parent epic** to file under, or context. Fetch it with `getJiraIssue` to confirm what it is before assuming.
- **Cloud ID:** pass the site hostname (e.g. `<site>.atlassian.net`) straight to the jira tools as `cloudId`. Only if that fails, call `getAccessibleAtlassianResources`.
- **Issue type:** default **Task**. Use `getJiraProjectIssueTypesMetadata` if unsure which types exist. File under an epic via the `parent` field.
- If you'd be **overwriting** an existing ticket's description, stop and confirm — don't clobber.

### 2. Scope against the repo

Briefly explore the actual codebase (Glob/Grep/Read) so the ticket names real files, not guesses. This research is for *you* — it informs tight bullets; it does not get dumped into the description.

### 3. Write it (honor the brevity contract)

- **Summary:** imperative, specific, no ticket-key prefix (Jira adds it).
- **Description:** plain markdown string (the MCP converts to ADF — never pass ADF JSON). Tight body — `## Work` + `## Acceptance` (+ `## Why` / `## Out of scope` if earned). Then, only if there's discovery worth keeping, a `---` followed by `## Technical Notes` where verbosity is allowed.
- Surface genuine forks/risks as a single line in the body; the supporting detail goes in Technical Notes.

### 4. Create + report

- `createJiraIssue` (set `parent` for epic children).
- Report the new key + URL and a one-line summary of what you filed. Don't paste the whole description back.

## Arguments

$ARGUMENTS
