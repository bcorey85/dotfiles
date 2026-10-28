---
type: "Change"
title: "`/code` step 3: the gate's lint command takes `{files:<suffixes>}` in place of the phase's path list"
description: "`/code` step 3: the gate's lint command takes `{files:<suffixes>}` in place of the phase's path list."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-19T00:00:00-05:00"}
seq: 4
components: ["skill/code", "script/coder-gate"]
evidence: ["judgment"]
watches: ["coder-gate-lint-changed-files"]
---

## Change

`/code` step 3: the gate's lint command takes `{files:<suffixes>}` in place of the phase's path list. `coder-gate.py` fills it at each hand-back with the files the coder changed (tracked changes against HEAD plus untracked files, relative to a leading `cd`). A command whose list is empty is skipped, and `clear` and the hand-back stamp name the skipped commands

## Evidence

judgment

### Anchor reasons

Anchor `skills/code/SKILL.md`, section `## Task` (evidence: removal round):

The argument placeholder. Byte-identical in both arms.

## Result

In a `/code` bench run, the coder moved route tests into `app.test.ts`, a file that the phase did not name. The gate lint named only `src/app.ts`, so the gate passed, and the full `eslint .` then failed on that file. A scratch test of the script passed 18 of 18 cases for the placeholder, the suffix filter and the skip, and the earlier 78 of 78 cases for the whole-package refusal. In 2 live `/code` runs the gate filled `{files:.ts}` at hand-back, and in one it caught an unused variable. Neither coder changed a file outside the phase, so the miss case did not recur.

## Watch

review findings per review run.

Reading, 2026-10-27 intake: WORSE, kept. Review findings per review run went from a 3.62 median (range 2.88–5.20) to 5.95. The first after bin, 2026-10-18 to 10-24, read 3.72, inside the before range. The whole rise sits in 2026-10-25 to 10-27 (9.55), and most of it on 10-27, when `/code` began running the review loop as a script with its own finding writer. That day logged 388 code-reviewer finding rows against 214 findings declared by its run rows. Without 10-27 the after window reads about 4.3, inside the before range. The metric cannot read this edit until the scripted loop's finding rows match its run rows. The watch is closed.

## Back-out

restore the path-list sentence in `/code` step 3. The script change acts only on a command that holds `{files}`
