---
name: save-note
description: Save or update a note in the Obsidian vault at ~/vault. Use when the user says "save note", "save this to obsidian", "make a note", "write a note", or "/save-note". Handles folder selection, template matching, and wikilink conventions.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion]
---

# Save Note to Obsidian Vault

Save or update a Markdown note in the user's Obsidian vault at `~/vault`.

## Vault Structure

| Folder | Purpose | Template file |
|--------|---------|---------------|
| `00. Inbox/` | Raw captures, quick thoughts, links | `Templates/Inbox.md` |
| `01. Literature/` | Processed source notes (articles, PDFs, videos) | `Templates/Literature.md` |
| `02. Permanent/` | Distilled standalone ideas with links | `Templates/Permanent.md` |
| `90. Projects/` | Active project notes | `Templates/Project Goal.md` or `Templates/Project Ideation.md` |
| `92. Resources/` | Reference material, cheat sheets | `Templates/Resource.md` |
| `93. Archives/` | Older archived notes | — |

Extra templates: `Templates/Scratch Note.md` (brain dumps), `Templates/MOC.md` (maps of content).

## Note Conventions

- **Title format**: `Topic - Title.md` (e.g., `AI - Transformer Architecture.md`, `DRF - Serializers.md`)
- Permanent notes may use question or concept format
- Internal links use `[[wikilink]]` syntax
- Replace `{{date}}` with today's date in `M/D/YYYY hh:mm A` format
- Fill in relevant template sections; remove unused optional ones

## Workflow

### Step 1: Determine content

Read the user's arguments. They may provide:
- A title and content directly
- A reference to conversation context (e.g., "save the summary above")
- A topic with minimal guidance

### Step 2: Choose folder and template

Match content type to folder:
- Quick thought, link, raw capture → `00. Inbox/` + Inbox template
- Summary of article, PDF, video, external source → `01. Literature/` + Literature template
- Distilled idea or concept → `02. Permanent/` + Permanent template
- Reference material, cheat sheet, how-to → `92. Resources/` + Resource template
- Brain dump, scratch work → `00. Inbox/` + Scratch Note template

If uncertain, ask the user with AskUserQuestion.

### Step 3: Check for duplicates

Use Glob to check if a note with a similar title exists. If found, ask whether to update or create new.

### Step 4: Create or update

1. Read the chosen template from `~/vault/Templates/`
2. Fill in template sections with content
3. Replace `{{date}}` with today's date (`M/D/YYYY hh:mm A`)
4. If the content originated from a URL, web search, PDF, or any external source, include the source URL(s) in the note. Templates with a `Source:` field should use that; otherwise append a `### References` section at the bottom with source links.
5. Write to the appropriate folder with topic-prefix filename

### Step 5: Confirm

Report: file path relative to vault root, template used, and any `[[wikilinks]]` added.
