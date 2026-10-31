---
type: "Change"
change_type: "changed"
title: "The performance reviewer now also flags unbounded single-object reads"
description: "The performance reviewer's scope list gained one bullet on unbounded single-object reads (26 words, 694 in the agent file): a whole file, blob, or response body read into memory, or returned to a caller, with no size bound or streaming."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-19T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/perf-reviewer"]
evidence: ["seeded round"]
watches: []
---

## Change

The performance reviewer's scope list gained one bullet on unbounded single-object reads (26 words, 694 in the agent file): a whole file, blob, or response body read into memory, or returned to a caller, with no size bound or streaming. The opencode copy got the same bullet, with no measurement on its model. The deep variant reads the base file, so it inherits the bullet.

## Evidence

seeded round

## Result

On a planted handler that reads a whole file into memory, the reviewer with the bullet named the read in every run and filed it as a fix in nearly every run. Without the bullet it named the read in most runs but never as a fix: a third of the runs asked the user, a third left an optional closing note, and a third missed it. In the review loop a fix reaches the fix pass, a question goes to the user, and a closing note is dropped. Over two rounds the bullet gave a fix in more than half of the runs, and the old text gave none. On a twin tree where the handler streams the file, no run with the bullet flagged it. The other planted defects were found at least as often with the bullet, and the tokens of a review did not rise in any type: fresh, cache read, and output were level or slightly lower. The gain is quality at equal token cost, for 26 always-loaded words in each performance review. The registered rule of the round said hold. It needed the old text to miss the read in nearly every run, as it did before, and a harness update made the reviewer read the changed files whole, so the old text named the read in most runs. The fix-level count came after the fact, and the edit went in on the user's word. Reach limit: the diff trigger of the performance pass needs a database dependency in the repo and a query-surface match in the diff, so a diff with only a whole-file read does not start the pass. The bullet acts when the pass already runs, by trigger, by plan declaration, or by the force flag. The trigger did not change, because nothing measured a wider one.

## Watch

—

## Back-out

—
