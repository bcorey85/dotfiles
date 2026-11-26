---
type: "Change"
change_type: "added"
title: "Scripts CLAUDE.md names the owner of the dirty-file holder"
description: "The owners list in the toolkit scripts guide now points to the module that names which live session wrote a repo's dirty files, with the cutoff commit it reads, so a later edit reuses it in place of naming a holder by working folder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T02:06:34-06:00"}
seq: 2
kind: "user-rule"
components: ["rule/scripts-claude-md", "script/dirty-writers"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-22: the user set that a session writes an owner line in the toolkit scripts guide on its own, with a change file"
proof: []
unmeasured: "An owner line is a pointer to a module, and the rule that governs it exempts it from a meter run. No intake number reads it."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`claude/.claude/scripts/CLAUDE.md`, Owners: one line added after the shared-clones line. Which live session wrote a
repo's dirty files (a transcript write on a dirty path after a cutoff commit: HEAD, or a start record's head) is owned
by `lib/dirty_writers.py` (`dirty_writers`, `holder_with_paths`); never name a holder by working folder alone.

## Evidence

- judgment: the holder-by-writer branch moved holder naming into `lib/dirty_writers.py` with no owner line, and its
  review asked for one that names the cutoff commit. The ask was dropped by a stale flag, so it was queued.

## Result

One line added. The rule-anchor check and the change builder pass.

## Watch

None: see `unmeasured`.

## Back-out

Delete the line.
