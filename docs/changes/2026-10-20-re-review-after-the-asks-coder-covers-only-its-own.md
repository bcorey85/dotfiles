---
type: "Change"
title: "Re-review after the asks coder covers only its own diff"
description: "After the user rules on review asks and a coder applies them, the next review reads only the files that coder changed. A docs-only asks diff ends the phase with no review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T17:51:16-05:00"}
seq: 4
components: ["script/code-step"]
evidence: ["judgment", "census"]
watches: ["asks-coder-own-diff-review"]
---

## Change

`code-step.py after-coder`, on an asks-coder return:

- The review file list is the set of files whose hash changed between the asks-coder dispatch snapshot (`asksBaseline`) and now. Before, it was every file the phase changed.
- If every file in that list ends in `.md`, `.mdx`, `.rst` or `.txt`, no review runs. The phase finishes through `finish_phase`, which also tells the fork to mark the review gate clean.
- The carried why-notes go only to files in the narrowed list.
- A state saved before `asksBaseline` existed keeps the whole-phase scope.

The first coder run of a phase still gets a review of every file the phase changed. So each coder run gets exactly one review of its own work, which was the flow before the coder loop.

## Evidence

Judgment and a session census. Each asks-coder triggered a fresh whole-phase review with the round counters reset. Each full pass sampled older code again and raised a new ask, and that ask started another asks-coder. One planned phase ran 12 reviews in about 2 hours 10 minutes. Six of the 12 came after an asks-coder that changed only spec text. The behavior came in with the first commit of the script.

The repeat passes also found 4 real defects (2 medium, 2 low) that the first pass missed. This change does not keep that yield. The fix for first-pass recall belongs in the reviewer, not in a review loop that never ends.

## Result

`test_code_step.py` passed 69 of 69 against the patched script, with three new tests: the narrowed re-review list, the docs-only finish, and the full list on the first coder run. `test_code_step_termination.py` found 0 paths that fail to end.

## Watch

`asks-coder-own-diff-review`: review escapes per code-reviewer run, expected flat. Fewer re-review runs push this ratio up with no change in escapes, so read the raw escape count next to it.

## Back-out

Restore the installed `code-step.py` from git. The change is the `asks_coder_changed_files` helper and the block after the no-change stop in `command_after_coder`.
