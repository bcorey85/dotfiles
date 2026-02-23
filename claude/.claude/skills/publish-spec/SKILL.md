---
name: publish-spec
description: PM command — publish a feature spec to Notion. Use after /feature-plan or with a quick description.
allowed-tools: [Read, Glob, Grep, Bash, Task, mcp__notion__notion-search, mcp__notion__notion-fetch, mcp__notion__notion-create-pages, mcp__notion__notion-update-page]
---

# Publish Feature Spec

Publish a feature spec to the Notion Specs database. This is a PM-side command — it only touches Notion. Use `/create-ticket` afterwards to generate Jira tickets from the spec's acceptance criteria.

## Instructions

### Step 1: Determine the Source

The input may be one of:

- **A `/product-specs/*.md` file** (output of `/feature-plan`) — this is the richest source. Read and extract from it.
- **A brief description** ("task filtering API") — you'll write the spec content yourself.

**Check for existing product specs first:**
- Glob `/product-specs/*.md` for files matching the feature name
- If found, ask the user: "Found `product-specs/task-filtering.md` — want me to publish this to Notion?"
- If multiple matches, let the user choose

### Step 2: Extract Spec Content

**If publishing from a `/product-specs/` file:**
- Read the file
- Extract: Problem Statement, Approach (from the architecture sections), Acceptance Criteria (from Success Criteria + scope), and Open Questions
- Condense the multi-agent output into the Notion spec template format — the Notion spec should be a concise summary, not a copy of the full feature plan

**If writing from scratch:**
- Use the user's description to draft the spec sections
- Follow the template: Problem → Approach → Acceptance Criteria → Jira Tickets → Open Questions

### Step 3: Create the Notion Spec

Create the spec page in the Specs database using `notion-create-pages`:
- Parent: the Specs DB data source (read `NOTION.md` for the ID)
- Properties:
  - **Name**: feature name
  - **Status**: "Draft"
  - **Type**: "Spec" (or "Design"/"RFC" if appropriate)
  - **Priority**: High/Medium/Low based on context
- Content follows the template structure:
  - **Problem** — what are we solving, why it matters
  - **Approach** — how we'll solve it, key technical decisions
  - **Acceptance Criteria** — concrete, checkable items
  - **Jira Tickets** — placeholder (filled by `/create-ticket`)
  - **Open Questions** — unresolved decisions

If publishing from a product spec, also add a reference line:
> Source: `/product-specs/<filename>.md`

### Step 4: User Review

Show the spec to the user and ask if they want to:
- **Edit** anything
- **Create Jira tickets now** — suggest running `/create-ticket`
- **Leave as Draft** for now

### Step 5: Summary

Present:
- Link to the Notion spec
- Suggested next step: "Run `/create-ticket` to generate Jira tickets from the acceptance criteria"

## Pipeline Context

This command sits in the PM pipeline: `/feature-plan` → **`/publish-spec`** → `/create-ticket`. After publishing, suggest the user run `/create-ticket` to generate Jira tickets from the acceptance criteria.

## Arguments

$ARGUMENTS
