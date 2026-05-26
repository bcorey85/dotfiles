---
name: q-questions
description: Generate objective research questions from a ticket (QRSPI step 1 of 5)
allowed-tools: [Bash, Read, Glob, Grep, Write, AskUserQuestion]
---

# Generate Research Questions

Transform a ticket/task description into focused research questions that will guide objective codebase exploration. This is step 1 of the QRSPI workflow (Questions -> Research -> Design -> Structure -> Plan).

QRSPI is for larger features where a monolithic plan would skip steps or leak opinions. For small/medium tasks, prefer `/eng-spec` instead.

## Why This Step Exists

Research quality degrades when the model knows what's being built — it injects opinions into what should be objective facts. This step acts as a "query planner": translate the ticket into questions that touch all relevant code, then hand ONLY the questions to the research step. The ticket stays hidden from research.

## Task Directory & Ticket Detection

All QRSPI artifacts for a task live together in one directory under `docs/eng-specs/`:

```
docs/eng-specs/IQ-XXX-short-description/
├── IQ-XXX-00-ticket.md       <-- ticket snapshot (you create this if a ticket was provided)
├── IQ-XXX-01-questions.md    <-- you create this
├── IQ-XXX-02-research.md
├── IQ-XXX-03-design.md
├── IQ-XXX-04-structure.md
└── IQ-XXX-05-plan.md
```

**Detect the ticket from the current branch first:**

```bash
git rev-parse --abbrev-ref HEAD
```

Branches follow `TICKET-NUM-description` (e.g., `iq-400-frontend-ts-migration` → ticket `IQ-400`). Extract via:

```bash
git rev-parse --abbrev-ref HEAD | grep -oE '^[a-zA-Z]+-[0-9]+' | tr '[:lower:]' '[:upper:]'
```

- If the branch yields a ticket, use it (e.g., `IQ-400`) and derive a slug from the rest of the branch name.
- If the branch has no ticket prefix (e.g., `feature/foo`), check the conversation context for a ticket. If still none, ask the user: "I couldn't detect a ticket from the branch. What's the ticket number, or should I create a slug-only directory?"
- Create the directory if it doesn't exist.

## Process

1. If no input provided, ask for a ticket path or task description, then wait.
2. Read any provided ticket/file FULLY (no limit/offset).
3. Detect the ticket from the current branch (see above).
4. **Snapshot the ticket** to `docs/eng-specs/IQ-XXX-description/IQ-XXX-00-ticket.md` so the task folder is self-contained:
   - If the user passed a file path, copy its contents verbatim.
   - If the user pasted ticket text in the conversation, write that text.
   - If only a Jira key/URL was provided, suggest running `/pull-ticket` first to pull Jira context locally, then re-run `/q-questions`.
   - Skip this step if a ticket file already exists at that path (don't overwrite — ask first).
5. Identify the components, patterns, and systems the ticket touches.
6. Generate 5-12 research questions.
7. **Write the questions to disk immediately** at `docs/eng-specs/IQ-XXX-description/IQ-XXX-01-questions.md`.
8. Print the short footer (see "After Writing" below) and ask the user if they want any edits to the questions before moving on.

## Question Rules

- Frame every question as "document what exists" — never "how to change/build".
- Each question targets a specific area or vertical slice of the codebase.
- Cover: data flow, types/interfaces, existing patterns, test patterns, error handling.
- Order from foundational (data/types) to surface (UI/API).
- NEVER mention what is being built or why in the question text.
- A skilled engineer reading these questions should know exactly which codebase areas the research will explore.

## Saved File Format

Write the questions file as a numbered list with an exploration map. The file on disk is the source of truth:

```
# IQ-XXX Research Questions

1. How does the [component] system work? Trace the data flow from [entry] to [exit].
2. What types and interfaces exist for [entity]? Where are they defined?
3. How do existing [similar feature] implementations handle [pattern]?
4. What test patterns exist for [area]? Where are the test files?
...

## Exploration Map

- `worker/src/[module]/` — [why]
- `frontend/src/components/[area]/` — [why]
- `worker/src/[entrypoint]` — [why]
```

## After Writing

After saving, print this short footer and ask if the user wants any edits. Do NOT copy-paste the questions inline — the file on disk is the source of truth.

```
Saved → docs/eng-specs/IQ-XXX-description/IQ-XXX-01-questions.md

Want any edits to the questions? Otherwise, run /clear, then /q-research docs/eng-specs/IQ-XXX-description/
```

Substitute the real path.

If the user requests edits, update the saved file directly (use the Edit tool) and re-print the footer. Do NOT regenerate from scratch unless asked.

Do NOT include any ticket context, goal descriptions, or implementation intent in the saved questions.

## What NOT To Do

- Do NOT run any codebase research yourself — that is step 2.
- Do NOT include opinions about implementation approach in the questions.
- Do NOT reference the ticket's goals in the question text.
- Do NOT generate more than 12 questions — focus beats breadth.
- Do NOT suggest skipping this step to save time — this separation is the whole point.

## Arguments

$ARGUMENTS
