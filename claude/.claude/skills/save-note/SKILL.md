---
name: save-note
description: Capture a note into the Obsidian vault at ~/vault. Use when the user says "save note", "save this to obsidian", "make a note", "write a note", or "/save-note". Writes to exactly one place — notes/ — because information always goes there and never into a project folder or cache/.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# Save Note to Obsidian Vault

Save or update a Markdown note in the vault (`$VAULT_DIR` else `~/vault`; paths below relative to it).

## The vault is a cache hierarchy

| Folder      | Holds                                              | This skill                 |
| ----------- | -------------------------------------------------- | -------------------------- |
| `cache/`    | consolidated answers, synthesized at project close | **never writes here**      |
| `notes/`    | all raw information, flat                          | **the only destination**   |
| `projects/` | goals, roadmaps, decisions, status — orchestration | **never writes here**      |
| `daily/`    | generated recap                                    | compiled by `/daily-recap` |

## Step 1: There is no routing decision

**This skill writes to `notes/`. That is the whole of step 1.** Never `cache/` or project folders, under any circumstance.

Projects are an **orchestration layer** — they link notes, never contain them. Project-surfaced material is still a note; link the project into it.

**`cache/` is synthesis, not capture** (different acts, not confidence levels). Capture is this skill (cheap, frequent). Synthesis is deliberate consolidation when a project wraps or a need arises.

Explicit `cache/` request means say so and do it as ordinary synthesis work, not through this skill.

**Never ask which folder** — there is nothing to ask: the answer is always `notes/`.

### Verification is marked, not filed

Nothing splits by confirmation — write the note, mark told-not-shown lines `[unverified]` (greppable, terminal-plain):

```markdown
- Handlers run once, at the end of the play, in declaration order.
- Handler ordering ignores notify order entirely. [unverified]
```

`[unverified]` is greppable and reads plainly in a terminal.

## Step 2: Tag

**At most one tag per note.** Current vocabulary, from the vault's `CLAUDE.md`:

```
#backend   #devops   #architecture   #llms   #linux
```

Read that list from `CLAUDE.md` live — open and growing. Most notes need no tag — filename prefixes are the taxonomy, search covers the rest.

**The tag is a retrieval handle:** what the user would type when looking. Never the correct-reading tag over the searchable one (`#linux` for the machine they use, not `#devops`).

**You may add a tag** unasked (the searchable word); add to `CLAUDE.md` same turn. No minimum count; singletons cull later.

**Never synonym-tags** — two handles split recall.

Do not propose a grooming pass on the tag list.

## Step 3: Name and write

- **Filename**: `Topic - Title.md` (`AI - Transformer Architecture.md`,
  `DRF - Serializers.md`). The prefix is load-bearing — it is the taxonomy.
- `notes/` is **flat** — never subfolders. The prefix is the taxonomy.
- Internal links use `[[wikilink]]` syntax, matched by note name, not path.
- **If a project surfaced this, link the project from the note** — a
  `[[Goal - Agent Memory]]` or `[[Postgres Foundations - Learning Path]]` line. That
  link is what replaces filing it in the project folder, so it is not optional.
- Templates in `Templates/` optional; use if fitting. `{{date}}` = today in `M/D/YYYY hh:mm A`.
- If the content came from a URL, web search, or PDF, include the source link —
  in a `Source:` field if the note has one, else a `### References` section.

Before writing, Glob for a similar title. If one exists, update it rather than
creating a near-duplicate.

## Step 4: Confirm

Report vault-relative path, tag, added wikilinks.
There is no tier to justify — the destination is always `notes/`.

## When the design itself is the problem

Note not belonging, or a rule fighting capture: one line in `vault-redesign/friction.md`. Record, never redesign.

## Constraints

No promotion ladder — never suggest a grooming pass, an
inbox-zero sweep, or proactive distillation. Cache entries get written when a
project wraps or a need arises, never on a schedule.
