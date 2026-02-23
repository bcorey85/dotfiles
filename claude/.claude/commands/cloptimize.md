---
description: Meta-reflection — analyze the current conversation and recommend optimizations to instruction files (CLAUDE.md, skills, agents, memory)
allowed-tools: [Task, Read, Write, Edit, Glob, Grep, AskUserQuestion]
---

# Cloptimize

Analyze the current conversation for friction, corrections, and missed opportunities. Recommend concrete edits to behavior-directing files. Never make changes without user approval.

## Modifiers

- `+deep` — Include lower-severity polish recommendations (naming, wording, minor restructuring). Also suggest new skills or agents that should be created.
- `+quick` — Analyze only the last 3-5 exchanges. Uses Sonnet model. Skip reading all behavior files — only read files referenced in the recent conversation.

## Instructions

### Step 1: Launch the-cloptimizer Agent

Use the Task tool with `subagent_type: "the-cloptimizer"`.

**If no arguments provided (full conversation scan):**
- Instruct it to analyze the entire conversation for optimization opportunities
- Default model (Opus) — no override needed

**If arguments provided:**
- Pass the arguments as a focus query: "Focus your analysis on this interaction: [ARGUMENTS]. Locate the relevant portion of the conversation, quote the user message(s) you identified, and analyze that segment. Still read all behavior files — the fix could be anywhere."

**If `+deep` modifier:**
- Add to the prompt: "Include LOW severity recommendations for polish and minor improvements. Also evaluate whether new skills or agents should be created, and whether any existing ones should be deprecated."
- Strip `+deep` from the prompt

**If `+quick` modifier:**
- Pass `model: "sonnet"` to the Task tool call
- Add to the prompt: "Analyze only the last 3-5 exchanges in the conversation. Only read behavior files that are directly referenced or relevant to those exchanges — skip the full corpus scan."
- Strip `+quick` from the prompt

### Step 1b: Framework-Specific Content Gate (MANDATORY)

Before presenting recommendations to the user, scan EVERY proposed change targeting a skill file (`~/.claude/commands/*.md`) or agent file (`~/.claude/agents/*.md`) for framework-specific content. This includes:
- Runtime/package manager commands (`bun`, `npm`, `pip`, `cargo`, etc.)
- Framework names (NestJS, Django, Vue, React, Express, etc.)
- Language-specific patterns (decorators, hooks, middleware, etc.)
- Specific test runners (Jest, Vitest, pytest, etc.)
- Technology-specific file extensions (`.vue`, `.tsx`, `.py`, etc.)

If ANY recommendation targeting a USER-SCOPED file (`~/.claude/commands/` or `~/.claude/agents/`) contains framework-specific content, **rewrite it to be generic before presenting**. Use phrasing like "Run the project's test suite (refer to CLAUDE.md for commands)" instead of "Run `bun run --filter api test`". The user has corrected this behavior MULTIPLE TIMES. Do not let it through.

**Exception:** Framework-specific content IS allowed in project-scoped files: CLAUDE.md, project MEMORY.md, and project-local agents/skills (files inside the repo). The gate only applies to user-scoped files shared across projects.

### Step 2: Present Recommendations

Format the agent's output as a numbered menu for the user. Group by severity (CRITICAL first):

```
### [N]. [SEVERITY] — `[target_file]` — [one-line summary]

**What happened:** [description from agent]
**Why it matters:** [impact from agent]

**Proposed change to `[filename]`:**
\```diff
- old line
+ new line
\```

**Rationale:** [from agent]
```

After all recommendations, show:
```
Found [N] recommendations: [X] critical, [Y] high, [Z] medium, [W] low
```

### Step 3: Wait for User Approval

Ask the user which recommendations to apply. Accept:
- Specific numbers: "1, 3, 5"
- All: "all"
- None: "none"
- Partial with modifications: "1, 3 but change the wording on 3 to..."

Do NOT proceed without explicit approval. This is non-negotiable.

### Step 4: Apply Approved Changes

For each approved recommendation:
1. Read the target file to get its current state
2. Apply the edit using Edit (for modifications) or Write (for new files)
3. If the user requested modifications to a recommendation, incorporate their feedback before applying

### Step 5: Summary

Present:
- Which recommendations were applied (file paths)
- Which were skipped
- Any follow-up suggestions (e.g., "Test `/pull-ticket` to verify the fix")

## Optimization Targets

The cloptimizer can recommend changes to:
- `CLAUDE.md` (project root)
- `~/.claude/commands/*.md` (skill files)
- `~/.claude/agents/*.md` (agent definitions)
- `~/.claude/projects/*/memory/MEMORY.md` (project memory)
- `~/.claude/agent-memory/*/MEMORY.md` (per-agent memory)
- NEW skill or agent files (in `+deep` mode)

## Arguments

$ARGUMENTS
