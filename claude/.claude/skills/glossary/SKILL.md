---
name: glossary
description: Look up a domain term in the project's glossary, build a glossary from the code when none exists, or find terms the code spells several ways. Use when the user asks what a term means here, whether a name already exists, which word to use for a concept, or to unify naming. Triggers on "/glossary", "is there a term for", "what do we call", "glossary setup", "divergent terms", "unify naming".
---

# Glossary — the project's domain words

Three modes, picked by the first argument:

- `/glossary <term or question>`: look up.
- `/glossary setup`: build `docs/glossary.md` from the code.
- `/glossary drift`: find concepts the code names more than one way.

The skill works on a repo with no glossary file. Never require one, and never write one outside `setup`.

## Find the glossary

Search the repo for `glossary.md`, any case, skipping `node_modules`, `vendor`, `.git` and build output:
`rg --files -g '!node_modules' -g '!vendor' --iglob '*glossary*.md'`. Several hits: use `docs/glossary.md` if present,
else the one nearest the repo root, and name the others.

Write every entry you add to an existing glossary in that file's own format, never the format below.

## Look up

1. Read the glossary and match the term, its plural, its other word forms (verb, noun, adjective), and every alias the
   glossary lists.
2. Search the code for the term: identifiers in camel, snake, kebab and Pascal case, table and column names, route
   paths, UI strings.
3. Answer in one of four ways, with `file:line` evidence:
   - **Defined**: quote the entry, and name where the code uses it.
   - **Alias**: the term is a listed alias of another; name the canonical term to use.
   - **In code, not in glossary**: give its meaning from the code that defines it, and offer to add the entry.
   - **Nowhere**: say so, and name the closest existing terms, so a new name does not duplicate one.

No glossary file: answer from the code alone, say no glossary exists, and offer `setup`.

## Setup

A glossary already exists: do not overwrite it. Run drift against it and offer the missing entries as a list.

Otherwise, scan the code for domain words, in this order:

1. Data models: ORM models, schema and migration files, table names, enum names and their values.
2. API surface: route paths, request and response types, event and queue names.
3. Business logic: service and module names, the verbs in their public functions (`approve`, `settle`, `void`).
4. Words in the README, `docs/`, and UI strings.

Keep a word when it names a business concept the code builds on. Drop framework and generic words (`handler`,
`utils`, `data`, `manager`). Use an Explore subagent for the sweep on a large repo, and read the defining code yourself
for each kept word.

Write `docs/glossary.md`, one heading per term, sorted A to Z. Never a Markdown table:

```
# Glossary

## Terms

### Settlement

*noun* · `billing/models.py:41`

The payout of a closed auction to the seller, net of fees.

Avoid: payout, disbursement

### settle

*verb* · `billing/service.py:88`

Create the settlement for a closed auction.

Avoid: pay out, disburse
```

- Kind: noun, verb, adjective, state or event. A noun and its verb are two entries.
- One plain sentence of meaning, read from the code, never guessed from the name. A meaning you could not confirm gets
  `(unconfirmed)` and goes in your report.
- `Avoid:` lists the other names drift found for the same concept. Leave the line out when there are none.
- Put every drift item that has no clear winner under a closing `## Open naming questions` heading, not under
  `## Terms`.

Then leave a breadcrumb, only when this run created the glossary: append to the repo's root `CLAUDE.md` one line,
`Domain terms: docs/glossary.md. Use its canonical names; never an alias it lists.` Skip it when the file already
points at the glossary. No `CLAUDE.md` exists: do not create one, and say so in the report.

Report the term count, the unconfirmed count, the open questions and whether the breadcrumb went in. Do not commit.

## Drift

Find concepts the code names more than one way, and names that mean more than one thing:

- **Synonyms**: one concept, several words (`customer`, `client`, `account holder`).
- **Verb drift**: one action, several verbs (`create`, `add`, `new`, `register` for the same insert).
- **Layer drift**: one field named differently across layers (column `amt_cents`, API `amount`, UI "Total").
- **Overloaded word**: one word, two concepts (`order` as purchase and as sort order).
- **Stale entry**: a glossary term the code no longer uses, or a listed alias the code still uses.

Confirm each item by reading the defining code at both names: two names count as drift only when they hold the same
concept. Count each name's uses.

Output, worst first (most uses split across names):

```
1. <concept> — <name A> (n uses), <name B> (n uses). Canonical: <name>. Kind: <noun | verb | …>. Evidence: `file:line`, `file:line`.
```

- Pick the canonical name by the glossary first, then the ticket and user-facing words, then the most uses.
- No clear winner: say `Canonical: user decides` and give the trade.
- Never rename code here. A rename across files goes to `/refactor`; adding the canonical name and its aliases to the
  glossary is the only edit this mode offers.

End with: `Reply with numbers to add to the glossary, or to send to /refactor.`
