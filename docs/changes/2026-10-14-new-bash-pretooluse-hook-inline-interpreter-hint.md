---
type: "Change"
title: "New Bash PreToolUse hook `inline-interpreter-hint.py`: denies exactly the inline interpreter runs the"
description: "New Bash PreToolUse hook `inline-interpreter-hint.py`: denies exactly the inline interpreter runs the generated safety gate blocks, with text naming the way around (write a scratchpad file and run it; run the interpreter step as its own call when no inline code runs)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-14T00:00:00-05:00"}
seq: 2
components: ["script/inline-interpreter-hint"]
evidence: ["census"]
watches: ["inline-interpreter-hint-hook"]
---

## Change

New Bash PreToolUse hook `inline-interpreter-hint.py`: denies exactly the inline interpreter runs the generated safety gate blocks, with text naming the way around (write a scratchpad file and run it; run the interpreter step as its own call when no inline code runs). It runs the gate's patterns through the system grep, so it matches the gate on macOS and Linux alike

## Evidence

census

## Result

Work block log: 649 interpreter-inline blocks since Aug 31, the top block reason, 12.8 a day after Oct 3. 35% follow another block within 10 minutes; the gate's own text names no other path, and the gate is generated and marked do not edit. Check: agrees with the gate on 12 of 12 test commands; would deny 538 of the 649 logged commands with Linux grep; the other 111 match only when the rule runs past `                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `, `;`and`&&`, as macOS grep does, so the work machine denies all 649 (not run on macOS here).

## Watch

interpreter-inline blocks per day, and the share within 10 minutes of the previous block, in the next intake.

Read 2026-10-24 on the work block log through 2026-10-22: interpreter-inline blocks per day fell from a median of 11.07 (range 8.14 to 27.86) to 8.11. Better. Kept. Watch closed.

## Back-out

remove the hook entry from `settings.json`
