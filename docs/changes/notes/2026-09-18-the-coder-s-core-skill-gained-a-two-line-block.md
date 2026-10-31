---
type: "Change"
change_type: "changed"
title: "The coder's core skill now tells the coder to copy import paths from existing imports or the module manifest"
description: "The coder's core skill gained a two-line block about import paths (30 words, 683 in all): before the first import of one of the repo's own packages, copy the import path from an existing import or the module manifest."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 15
kind: "behavior"
components: ["skill/coder-core"]
evidence: ["census", "seeded round"]
watches: []
---

## Change

The coder's core skill gained a two-line block about import paths (30 words, 683 in all): before the first import of one of the repo's own packages, copy the import path from an existing import or the module manifest. The two coder agent files did not change.

## Evidence

census, seeded round

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## Copy import paths, never guess them` (evidence: census, seeded round):

Before the first import of one of the repo's own packages, copy the path from an existing import or the module manifest. In a census of coder runs on a Go repo, about one run in three wrote a guessed import path first. Nearly no such run saw the module path before the write, and nearly every run that saw it first wrote it right. Each wrong guess cost a denied in-place shell edit, a file edit, and a second check: about a seventh of all coder tokens, nearly all cache read. In a later seeded round with the block in the text, wrong first imports fell to about one run in thirty, and the fix turns fell to under 2% of coder tokens. That is about 24 thousand tokens less for each coder run, nearly all cache read.

## Result

In a census of coder runs on a Go repo, about one run in three wrote a guessed import path first: the bare repo name, or a host path with the wrong owner. Of the runs that did not see the module path before the write, about four in five guessed wrong. Of the runs that saw it first, nearly none did. Most coders that guessed did read the module file, in the same call as the write, so the read came too late. Each wrong guess then cost a median of three more turns: an in-place shell edit that the shell-write hook denies, a file edit, and a second check. That is about 88 thousand Sonnet tokens per wrong run, nearly all cache read, and about a seventh of all coder tokens in the census. Without those turns a run that guessed wrong cost no more than the others. No output quality changed: every such run ended with the right path. Measured after the edit, in a seeded coder round on the same repo with the block in every run: wrong first imports fell from about one run in three to about one run in thirty, and nearly every run saw the module path before its first write. The fix turns fell from about a seventh of all coder tokens to under 2%. That is a gain of about 24 thousand Sonnet tokens and about 0.8 turns for each coder run, nearly all of it cache read, and the median coder run took about a seventh fewer tokens than before. Wall-clock did not change. The comparison is between rounds and not inside one wave, with an equal brief, model, and harness version, and chance gives a fall this large about one time in ten thousand. Only one other denied in-place edit showed in the census, so a general rule against them has no backing.

## Watch

—

## Back-out

—
