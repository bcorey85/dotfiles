---
type: "Change"
change_type: "removed"
title: "Remove the hook that forced agents to run in the foreground"
description: "The PreToolUse hook that set run_in_background to false on every Agent dispatch is gone. It did not hold, and the reason for it no longer exists: a subagent now gets the finish notice of its own background agents."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T08:03:30-05:00"}
seq: 6
kind: "behavior"
components: ["script/agent-foreground"]
evidence: ["census", "transcript read"]
watches: []
---

## Change

- Deleted `scripts/agent-foreground.py` and its test.
- Removed its PreToolUse Agent entry from `settings.json` and its reference in `tests/scripts/test_review_fixes.py`.

## Evidence

Census: on this machine, 195 of 214 review loops dispatched agents in the background although the hook was live. So the hook did not force the foreground.

Transcript read: the hook came in on 2026-09-15, when a subagent could not wait on a background agent because the finish notice went only to the main session. Review loops now end their turn after a background dispatch and get each report back as a task notification. The review-loop stop gate counts on that since 2026-10-21.

## Result

Staged 2026-10-21 in the script fix batch. Installed 2026-10-21.

## Watch

None. The hook wrote no rows, and no intake metric counts foreground and background dispatches.

## Back-out

Restore `agent-foreground.py`, its test and its `settings.json` entry from the dotfiles history.
