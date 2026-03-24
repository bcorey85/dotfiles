---
name: research
description: Research the best way to do something using web search. Use when the user says "research", "how should I", "what's the best way to", "look up", "what do the docs say about", or "/research". Also trigger when the user asks a technical question where the answer depends on current library versions, tool behavior, or ecosystem conventions that may have changed since training data. Do NOT trigger for questions answerable from the current codebase alone — use Grep/Read for those.
---

# Research

Investigate a technical question using web search and synthesize a concise, actionable recommendation with sources. Read-only — no code changes.

## Arguments

`<question>` — the topic or question to research. May be a full question ("how should I handle SSR with PrimeVue?") or a keyword topic ("vitest coverage v8 vs istanbul").

## Instructions

### Phase 1: Parse the Question

Extract the core question from `<question>`. Identify:
- **Subject**: the tool, library, or concept being asked about
- **Context**: any constraints from the current project (check CLAUDE.md and package.json if relevant)
- **Goal**: what the user wants to achieve or decide

If the question is vague, infer context from the current project before searching. For example, if the user asks "best testing approach" and the project uses Vitest + Vue, scope searches accordingly.

### Phase 2: Search Strategy

Run 3-5 WebSearch queries in parallel, varying the angle:

1. **Official docs**: `"<subject> official documentation <specific topic>"`
2. **Best practices**: `"<subject> best practices <year>" OR "<subject> recommended approach"`
3. **Community consensus**: `"<subject> <topic> site:github.com OR site:stackoverflow.com"`
4. **Comparisons** (if deciding between options): `"<option A> vs <option B> <context>"`
5. **Known issues** (if troubleshooting): `"<subject> <symptom> site:github.com/issues"`

Prioritize results from the current year. Discard results older than 2 years unless they're canonical references (RFCs, spec documents, foundational blog posts).

### Phase 3: Deep Dive

For the top 2-3 most promising results, use WebFetch to read the actual page content. Don't rely on search snippets alone — they often lack critical nuance, version constraints, or caveats.

Look for:
- Version-specific guidance (does the answer change between v3 and v4?)
- Official recommendations vs community workarounds
- Known gotchas or deprecation warnings
- Performance or security implications

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

- **Be opinionated.** The user wants a recommendation, not a balanced essay. Pick the best approach and say why. Mention alternatives briefly.
- **Flag uncertainty.** If sources conflict or the answer is genuinely "it depends", say so and explain what it depends on.
- **Include version context.** "As of PrimeVue 4.x..." or "This changed in Node 22..." — the user needs to know if the advice has a shelf life.
- **Prefer official sources.** Weight: official docs > maintainer comments on issues > high-score SO answers > blog posts > forum comments.
- **Skip the obvious.** Don't explain what the tool is or provide installation instructions unless the user specifically asked.
- **No code changes.** This skill is read-only. If the research reveals something actionable, tell the user what to do — don't do it. They can follow up with `/fix`, `/code`, or manual changes.
