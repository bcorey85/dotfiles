---
type: "Change"
change_type: "fixed"
title: "The comment-bloat gate checks only files inside a git repo"
description: "The comment-bloat gate blocks a write only when the file resolves into a git work tree. Scratch files, probes and temp scripts outside a repo are not committed code, and the gate blocked them."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T08:48:22-05:00"}
seq: 12
kind: "fix"
components: ["script/comment-bloat-gate", "script/script-utils"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `scripts/script_utils.py`: new `inside_git_work_tree(path, timeout)`. It resolves symlinks, then asks `git rev-parse --is-inside-work-tree`. If git cannot run, times out or exits with an error, it walks the parent folders for a `.git` entry. Files inside `.git` and inside a bare repo count as outside.
- `scripts/comment-bloat-gate.py`: on a marker leak or a density block, the gate runs the repo check first. A file outside a repo passes. The gate runs git only when it is about to block, so an edit that passes starts no git process.

## Evidence

Work incident: the gate flagged scratch probe files that the orchestrator and workers wrote outside any repo, and each flag cost a redo. A code review of the staged change found that a file symlink into a repo and a repo that git refuses for folder ownership escaped the check. It also found that the first version added 7 to 11 ms to every edit. All three were fixed before install.

## Result

Staged 2026-10-21 in the second script fix batch. 78 tests pass. Installed 2026-10-21.

## Watch

None. This gate does not write to the hook block log that the watch metrics read.

## Back-out

Restore the previous `comment-bloat-gate.py` and `script_utils.py` from the dotfiles history.
