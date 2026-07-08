---
name: weekly-recap
description: Roll the week's Daily notes into one weekly review note (decisions, themes, open follow-ups carried forward) and append achievement-phrased bullets to the yearly brag doc. Designed for a headless Friday-evening run (launchd/systemd via install/weekly-recap); also invocable manually with a date inside any target week.
---

# Weekly Recap

Compile one week of Daily notes into a weekly review. Idempotent: re-running for the same week rewrites that week's note from the same sources.

Vault root: `$VAULT_DIR` if set, else `~/vault`. Target week: the ISO week (Mon–Sun) containing the argument date if one was given, else today. Derive the label with `date +%G-W%V` (ISO year, not calendar year).

## Gather (read-only; skip any unavailable source gracefully — never fail the run)

1. **Daily notes**: `<vault>/Daily/<date>.md` for each day of the target week. Missing days are normal (weekends, PTO) — skip silently. These are the only source of raw material; do not re-query GitHub (the dailies already carry that day's PR activity).
2. **Carry-forward**: the previous week's note `<vault>/Weekly/<prev ISO week>.md`, section `## Open follow-ups` — collect its unchecked `- [ ]` items so open work persists week over week until checked.
3. Never fabricate content. A section with no source material gets `- none captured`.

## Write

Write `<vault>/Weekly/<ISO week>.md` (create the folder if needed). If the file
already exists and has a `## Focus` section, preserve it verbatim at the top —
the compile owns every other section, never that one:

```markdown
# Weekly Recap — <ISO week> (<Mon date> – <Fri date>)

## Decisions
- <deduped across the week, each tagged (Mon)/(Tue)/…; who/what/why when stated>

## Themes
- <patterns only visible across days: a roadblock or topic appearing on 2+ days,
  the same person/team recurring, a follow-up that keeps slipping. This is the
  lead-level synthesis — if nothing recurs, write `- none observed`>

## Shipped
- <merged PRs and completed work pulled from the dailies' My work sections>

## Open follow-ups
- [ ] <unchecked items from this week's dailies + carried from last week's note,
  deduped, each tagged with its origin date; drop any that a later daily shows
  as done — a `done:` capture or My work entry that matches the item>

## Brag
- <2–5 bullets, outcome-phrased for a promo packet: "Shipped X", "Unblocked
  team Y by Z", "Drove decision on W". Impact over activity>
```

Preserve people's names and ticket/PR references exactly. When a follow-up is ambiguous between open and done, keep it open — carrying a finished item one extra week is cheaper than dropping a live one.

## Brag doc

Append the `## Brag` bullets to `<vault>/Brag/<ISO year>.md` under a `## <ISO week>` heading (create file/folder if needed). If that heading already exists, replace its section instead of duplicating — the brag doc stays one section per week.

## Finish

Output exactly one line: the weekly note path plus counts, e.g. `~/vault/Weekly/2026-W28.md — 4 decisions, 2 themes, 7 open follow-ups (3 carried)`.
