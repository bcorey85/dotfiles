---
description: Create or update customer-facing documentation in Notion after shipping a feature
allowed-tools: [Read, Glob, Grep, Bash, mcp__notion__notion-search, mcp__notion__notion-fetch, mcp__notion__notion-create-pages, mcp__notion__notion-update-page]
---

# Update Customer Docs

Create or update customer-facing documentation in the Notion Docs section after shipping a feature.

## Notion Context

- Docs page: `30ed798c-c4fd-81d3-97a4-e6ad3f32f14f`
- Getting Started: `30ed798c-c4fd-817b-b7dc-e73221b7c4b6`
- API Reference: `30ed798c-c4fd-81cf-9ea0-d1a331a99edc`
- Guides DB data source: `c83c5e06-e528-4f7c-9e99-503c0764af0e`

## Instructions

1. **Determine what needs documenting** from the user's input. This may be:
   - A new feature that needs a guide ("document the task filtering API")
   - An API endpoint that needs reference docs ("update API reference for /tasks")
   - A getting started update ("add filtering to the quickstart")
   - A general instruction ("update docs for what we just shipped")

2. **If vague**, examine recent git history to understand what was shipped:
   ```bash
   git log --oneline -10
   ```
   Read the relevant source files to understand the feature.

3. **For API Reference updates**, read the actual code to generate accurate docs:
   - Find the route definitions and handlers
   - Document request/response shapes from the TypeScript types
   - Include examples

4. **For Guides**, create a new entry in the Guides DB:
   - Set Category (Setup/Usage/Integration/Troubleshooting)
   - Set Published to `__YES__` when ready
   - Write clear, step-by-step content

5. **For Getting Started updates**, fetch the current page first, then use `insert_content_after` or `replace_content_range` to update it.

6. **Show the user** what was created/updated with links.

7. **Log MCP usage** to `docs/mcp-usage.jsonl` for each tool call.

## Arguments

$ARGUMENTS
