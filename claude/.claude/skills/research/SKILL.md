---
name: research
description: Research the best way to do something using web search. Use when the user says "research", "how should I", "what's the best way to", "look up", "what do the docs say about", or "/research". Also trigger when the user asks a technical question where the answer depends on current library versions, tool behavior, or ecosystem conventions that may have changed since training data. Do NOT trigger for questions answerable from the current codebase alone — use Grep/Read for those.
---

# Research

Investigate a technical question using web search and synthesize a concise, actionable recommendation with sources. Read-only — no code changes.

## Arguments

`<question>` — full question or keyword topic.

## Instructions

### Phase 1: Parse the Question

Extract subject (tool or concept), context (project constraints — CLAUDE.md and package.json if relevant), goal (what the user decides).

Vague question means infer context from the project before searching.

### Phase 2: Search Strategy

Run 3-5 WebSearch queries in parallel: official docs angle, best-practices angle, community angle, comparisons if deciding, known-issues if troubleshooting.

Prefer current-year results; pre-2-year only if canonical (RFCs, specs).

### Phase 3: Deep Dive

WebFetch the top 2-3 results (never snippets alone).

- Version-specific guidance, official-vs-workaround, gotchas and deprecations, perf and security implications.

### Phase 4: Synthesize and Present

Present findings in this structure:

```
## Research: <topic>

### Recommendation

<1-3 sentences: what to do and why>

### Details

<Supporting evidence, code examples if relevant, version constraints>

### Alternatives Considered

| Approach | Pros | Cons |
|----------|------|------|
| ... | ... | ... |

### Sources

1. [Title](url) — <one-line summary of what this source contributes>
2. ...
```

### Guidelines

- **Be opinionated** — recommend, do not essay.
- **Flag uncertainty.** If sources conflict or the answer is genuinely "it depends", say so and explain what it depends on.
- **Include version context** (advice shelf life).
- **Prefer official sources.** Weight: official docs > maintainer comments on issues > high-score SO answers > blog posts > forum comments.
- **Skip the obvious.** Don't explain what the tool is or provide installation instructions unless the user specifically asked.
- **No code changes** — read-only. Actionable findings go to the user, not into the tree.
