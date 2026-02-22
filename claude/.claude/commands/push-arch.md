---
description: Push a local eng architecture doc to Notion Wiki
allowed-tools: [Read, Glob, Grep, Bash, mcp__notion__notion-search, mcp__notion__notion-fetch, mcp__notion__notion-create-pages, mcp__notion__notion-update-page]
---

# Push Architecture Doc

Push a local engineering architecture document from `/eng-arch/` to the Notion Wiki. Use this for cross-cutting decisions (ADRs, patterns, conventions) that should be shared and discoverable.

## Notion Context

- Wiki page: `30ed798c-c4fd-8105-8054-c6f729e3f049`

## Instructions

### Step 1: Find the Target File

If the user provides a filename or topic:
- Look for a matching file in `/eng-arch/`
- If no exact match, glob `/eng-arch/*.md` and suggest close matches

If no argument provided:
- List all files in `/eng-arch/`
- Ask the user which one to push

### Step 2: Read the Local File

- Read the full contents of the selected `/eng-arch/*.md` file

### Step 3: Check for Existing Notion Page

- Search Notion Wiki (`30ed798c-c4fd-8105-8054-c6f729e3f049`) for a page with the same or similar name using `notion-search`
- If found: confirm with user, then **update** the existing page using `notion-update-page`
- If not found: **create** a new page under the Wiki using `notion-create-pages`

### Step 4: Create or Update

**When creating a new page:**
- Parent: Wiki page `30ed798c-c4fd-8105-8054-c6f729e3f049`
- Title: derive from filename (kebab-case → Title Case)
- Content: the full markdown from the local file

**When updating an existing page:**
- Replace the content with the local file's content
- Preserve the page title unless the local file has changed it

### Step 5: Summary

Present:
- Notion page link (if available)
- Whether it was created or updated
- Remind the user that `/eng-arch/` docs are for cross-cutting decisions, not per-ticket plans

### Step 6: Log MCP Usage

Log each Notion tool call to `docs/mcp-usage.jsonl`.

## When to Use

- After making an architectural decision that affects multiple tickets
- When documenting a pattern or convention the team should follow
- When writing an ADR (Architecture Decision Record)
- NOT for per-ticket implementation plans (use `/eng-plan` for those)

## Arguments

$ARGUMENTS
