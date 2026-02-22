---
description: Add a changelog entry to the Notion Changelog database from recent commits or a version bump
allowed-tools: [Bash, Read, Glob, Grep, mcp__notion__notion-create-pages, mcp__notion__notion-fetch, mcp__notion__notion-search]
---

# Add Changelog Entry

Create a changelog entry in the Notion Changelog database based on recent commits or a version bump.

## Notion Context

- Changelog DB data source: `b355aefa-a396-4879-b948-344a05d6c2be`
- Type options: Feature, Fix, Improvement, Breaking

## Instructions

1. **Determine the version and scope** from the user's input:
   - If they specify a version: use it (e.g., "changelog for v0.2.0")
   - If not: check `package.json` for the current version, or ask

2. **Gather changes** to document:
   - If the user describes specific changes, use those
   - Otherwise, examine recent git history:
     ```bash
     git log --oneline <last-tag>..HEAD
     ```
   - If no tags exist, use recent commits since the last changelog-worthy point

3. **Categorize each change** as Feature, Fix, Improvement, or Breaking

4. **Create the changelog entry** in the Changelog DB using `notion-create-pages`:
   - Name: version number and brief summary (e.g., "v0.2.0 — Task Filtering")
   - Version: the version string
   - Date: today's date
   - Type: the primary category (if mixed, use the most significant)
   - Content: bulleted list of all changes, grouped by type

5. **Show the user** the created entry with a link.

6. **Log MCP usage** to `docs/mcp-usage.jsonl` for each tool call.

## Arguments

$ARGUMENTS
