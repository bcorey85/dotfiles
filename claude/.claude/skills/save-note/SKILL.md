---
name: save-note
description: Capture a note into the Obsidian vault at ~/vault. Use when the user says "save note", "save this to obsidian", "make a note", "write a note", or "/save-note". Writes to exactly one place — notes/ — because information always goes there and never into a project folder or cache/.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# Save Note to Obsidian Vault

Save or update a Markdown note in the user's Obsidian vault. Vault root: `$VAULT_DIR`
if set, else `~/vault` (matching `/orient`, `/daily-recap`, and `/vault-review`) —
all paths below are relative to it.

## The vault is a cache hierarchy

| Folder      | Holds                                              | This skill                 |
| ----------- | -------------------------------------------------- | -------------------------- |
| `cache/`    | consolidated answers, synthesized at project close | **never writes here**      |
| `notes/`    | all raw information, flat                          | **the only destination**   |
| `projects/` | goals, roadmaps, decisions, status — orchestration | **never writes here**      |
| `daily/`    | generated recap                                    | compiled by `/daily-recap` |

## Step 1: There is no routing decision

**This skill writes to `notes/`. That is the whole of step 1.** Never `cache/`,
never a project folder, under any circumstance — however thoroughly verified the
material is, however confident the user sounds, and however clearly it came out of
a project they are mid-way through.

Two rules produce that, and both were arrived at by getting it wrong:

**Information always goes to `notes/`, even when a project is what surfaced it.**
A page count measured in step 1 of a seven-step learning path is a fact about
Postgres, not a fact about the project. Filed in the project folder it becomes
unfindable — six months on, the lookup is "what did I learn about pages," not
"which project was I doing at the time." Projects are an **orchestration layer**:
goals, roadmaps, decisions, status. They _link_ to notes with `[[wikilinks]]`;
they do not contain them. If the material feels project-specific, it is still a
note — write the project link into it.

**`cache/` is written by synthesis, not capture.** Different acts, not different
confidence levels:

- **Capture** — what this skill does. Something came up and is worth keeping.
  Cheap, frequent, done without breaking flow.
- **Synthesis** — what makes a cache entry. A project wrapped, or a need arose, and
  one consolidated answer gets written deliberately from the material that
  accumulated in `notes/`. Rare, and never a side effect of learning something.

If the user explicitly asks for a `cache/` entry, say that `save-note` doesn't
write there and that a cache entry is a synthesis pass over the relevant notes —
then do that as ordinary work, not through this skill.

**Never ask which folder.** A modal at capture time is the friction this structure
exists to remove, and there is nothing to ask: the answer is always `notes/`.

### Verification is marked, not filed

Trust is a property of a claim, not of a location. Nothing is split across folders
by how well it was confirmed — write the note, and mark the lines that were told
rather than shown:

```markdown
- Handlers run once, at the end of the play, in declaration order.
- Handler ordering ignores notify order entirely. [unverified]
```

`[unverified]` is greppable and reads plainly in a terminal. It is what makes a
claim legible as a claim on the day the hit lands.

## Step 2: Tag

**At most one tag per note.** Current vocabulary, from the vault's `CLAUDE.md`:

```
#backend   #devops   #architecture   #llms   #linux
```

Read that list from `CLAUDE.md` rather than trusting this copy — the vocabulary is
**open and grows** as the user picks up new domains. Most notes need no tag at all:
the filename convention (`Ansible - Building Inventory`, `OS - Kernel`) is already
the topic taxonomy, and full-text search covers the rest.

**The tag is a retrieval handle, not a classification.** The only test is what the
user would type when going looking for this. `#linux` is for Linux as the machine
they use — a `chmod` reference, a Hyprland config, a pacman flag. `#devops` is
infrastructure work and is the wrong answer for those. Never reach for the tag that
reads correct over the one that would be searched.

**You may add a tag** without asking, when it is the word that would be searched.
Add it to `CLAUDE.md`'s list in the same turn — an undeclared tag is how drift
starts. There is **no minimum note count** to earn a tag: that would be a guess
about the note's future company, made at the one moment it cannot be answered.
Singletons get culled later, when the evidence exists.

**Never introduce a synonym of an existing tag.** Two handles for one interest
means half the notes miss on either query — that is the actual failure mode, not a
long list. `unix` was merged into `#linux`, `mcp` and `llm` into `#llms`.

Do not propose a grooming pass on the tag list. Culling singletons and merging
synonyms is retrospective and user-initiated, like everything else in `cache/`.

## Step 3: Name and write

- **Filename**: `Topic - Title.md` (`AI - Transformer Architecture.md`,
  `DRF - Serializers.md`). The prefix is load-bearing — it is the taxonomy.
- `notes/` is **flat**. Do not create subfolders in it, ever — not by topic, not by
  project, not "just for these few." The prefix is the taxonomy.
- Internal links use `[[wikilink]]` syntax, matched by note name, not path.
- **If a project surfaced this, link the project from the note** — a
  `[[Goal - Agent Memory]]` or `[[Postgres Foundations - Learning Path]]` line. That
  link is what replaces filing it in the project folder, so it is not optional.
- Templates in `Templates/` are optional scaffolding, not a requirement. Use one
  only if it fits; `{{date}}` becomes today's date in `M/D/YYYY hh:mm A`.
- If the content came from a URL, web search, or PDF, include the source link —
  in a `Source:` field if the note has one, else a `### References` section.

Before writing, Glob for a similar title. If one exists, update it rather than
creating a near-duplicate.

## Step 4: Confirm

Report the path relative to vault root, the tag, and any `[[wikilinks]]` added.
There is no tier to justify — the destination is always `notes/`.

## When the design itself is the problem

If the note genuinely did not seem to belong in `notes/`, or a rule here fought
the capture, append one line to
`projects/active/vault-redesign/friction.md` — what happened, what was ambiguous.
That file is where design defects get collected instead of being absorbed
silently. Do not redesign the hierarchy in the moment; record and move on.

## Constraints

No promotion ladder — a `notes/` entry that never becomes a `cache/` entry is
reference doing its job, not a backlog item. Never suggest a grooming pass, an
inbox-zero sweep, or proactive distillation. Cache entries get written when a
project wraps or a need arises, never on a schedule.
