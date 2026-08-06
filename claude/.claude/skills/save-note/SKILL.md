---
name: save-note
description: Save or update a note in the Obsidian vault at ~/vault. Use when the user says "save note", "save this to obsidian", "make a note", "write a note", or "/save-note". Routes on whether the material was verified or merely told, then writes with the right tag and wikilinks.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# Save Note to Obsidian Vault

Save or update a Markdown note in the user's Obsidian vault. Vault root: `$VAULT_DIR`
if set, else `~/vault` (matching `/orient`, `/daily-recap`, and `/vault-review`) —
all paths below are relative to it.

## The vault is a cache hierarchy

Three tiers, looked up in order when the user needs to do something:

| Folder      | Holds                                              | Admission test                                    |
| ----------- | -------------------------------------------------- | ------------------------------------------------- |
| `cache/`    | distilled answers, earned by doing                 | Would I want a hit on this — and did I verify it? |
| `sources/`  | material taken in without confirming it            | Was I told this rather than shown it?             |
| `projects/` | `active/` and `done/` — where new entries get made | Am I working on this?                             |
| `daily/`    | generated recap                                    | compiled by `/daily-recap`, never authored here   |

`cache/` entries are **derived and evictable** — a materialized view over
`sources/` and `projects/done`. Nothing there is the only copy of anything.

## Step 1: Route on one question

> **Did the user verify it, or were they told it?**

- Ran it, tested it, hit the failure, read the actual source → **`cache/`**
- Told it, read it, sounded right, never checked → **`sources/`**
- Working notes for something in flight → **`projects/active/<project>/`**

Provenance is not the axis; verification is. An LLM is an other and a session is a
source — a confident Claude Code answer the user never ran is `sources/`, not
`cache/`.

**Do not ask which folder.** A modal at capture time is the friction this
structure exists to remove. If genuinely torn, pick `sources/` — a wrong entry in
`sources/` is a miss that routes onward, while a wrong entry in `cache/` is a bad
hit that stops the lookup. That asymmetry is the whole reason the tier exists.

### Mixed notes

One note routinely mixes tiers. Do not split it across folders — file it by its
dominant claim and mark the unverified lines inline:

```markdown
- Handlers run once, at the end of the play, in declaration order.
- Handler ordering ignores notify order entirely. [unverified]
```

`[unverified]` is greppable and reads plainly in a terminal. It is what makes a
claim legible as a claim on the day the hit lands.

## Step 2: Tag

**Exactly one tag, from exactly four values — or none:**

```
#backend   #devops   #architecture   #llms
```

Never invent a fifth. Everything else is full-text search: the filename convention
(`Ansible - Building Inventory`, `OS - Kernel`) is already the topic taxonomy.
Frontend, OS, and tooling notes legitimately carry no tag.

## Step 3: Name and write

- **Filename**: `Topic - Title.md` (`AI - Transformer Architecture.md`,
  `DRF - Serializers.md`). The prefix is load-bearing — it is the taxonomy.
- `sources/` and `cache/` are **flat**. Do not create subfolders in them.
- Internal links use `[[wikilink]]` syntax, matched by note name, not path.
- Templates in `Templates/` are optional scaffolding, not a requirement. Use one
  only if it fits; `{{date}}` becomes today's date in `M/D/YYYY hh:mm A`.
- If the content came from a URL, web search, or PDF, include the source link —
  in a `Source:` field if the note has one, else a `### References` section.

Before writing, Glob for a similar title. If one exists, update it rather than
creating a near-duplicate.

## Step 4: Confirm

Report the path relative to vault root, the tier it landed in and why (verified vs
told), the tag, and any `[[wikilinks]]` added.

## Constraints

No promotion ladder — a `sources/` note that never becomes a `cache/` entry is
reference doing its job, not a backlog item. Never suggest a grooming pass, an
inbox-zero sweep, or proactive distillation. Cache entries get written when a
project wraps or a need arises, never on a schedule.
