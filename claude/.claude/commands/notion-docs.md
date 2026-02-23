---
description: Create or update customer-facing documentation in Notion after shipping a feature
allowed-tools: [Read, Glob, Grep, Bash, mcp__notion__notion-search, mcp__notion__notion-fetch, mcp__notion__notion-create-pages, mcp__notion__notion-update-page]
---

# Update Customer Docs

Create or update customer-facing documentation in the Notion Docs section after shipping a feature.

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

## Arguments

$ARGUMENTS
