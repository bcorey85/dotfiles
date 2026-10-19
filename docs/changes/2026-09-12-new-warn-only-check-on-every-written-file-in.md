---
type: "Change"
title: "New warn-only check on every written file: in documents it extracts each cited repository path and reports"
description: "New warn-only check on every written file: in documents it extracts each cited repository path and reports the ones that no longer resolve, plus line numbers past the end of the file they point into."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 3
components: ["script/stale-citation-gate"]
evidence: ["gate ranking"]
watches: []
---

## Change

New warn-only check on every written file: in documents it extracts each cited repository path and reports the ones that no longer resolve, plus line numbers past the end of the file they point into; in shipped source it reports planning vocabulary left in comments — phase numbers, decision ids, acceptance-criterion ids, author provenance, pointers into planning documents. It never blocks, and it never flags a path in a plan that the plan itself proposes to create, or a path whose own parent directory is absent from the repository, since that is a reference to some other tree rather than one this tree falsified.

## Evidence

gate ranking

## Result

A fifth of the defects the claim-checking discipline is aimed at need no judgment at all — a dangling citation and a banned vocabulary word are decided exactly by grep, and two of the recorded misses say so in their own description. A reader is the worse detector for them: it misses some, it cannot enumerate, and the attention it spends there is attention taken from the assertions that do need a reader. The existing vocabulary rule was written down and consumed by the reviewers but enforced only by their judgment, which is why instances of exactly its shape kept surviving review. Warn-only follows the precedent of the sibling prose check in the same slot: the signal is useful and imperfect, so a human triages each hit rather than having a write refused. Swept over a thousand documents in a corpus it was not tuned on, it flags three percent of files, and the residue is dominated by one pathology of that corpus — notes about upstream repositories whose files were never present — which no path heuristic can resolve and which the check cannot encounter in normal use, since it only ever sees the single file just written.

## Watch

—

## Back-out

—
