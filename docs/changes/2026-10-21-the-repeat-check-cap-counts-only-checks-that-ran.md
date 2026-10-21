---
type: "Change"
title: "The repeat-check cap counts only checks that ran and sees git changes"
description: "The quality-check cap denies a repeat check only when the earlier run surely ran and the working tree did not change. It sees git merges and commits, never denies a formatter that writes, and lets the review loop's gate run through."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T08:03:31-05:00"}
seq: 8
components: ["script/quality-check-cap"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `scripts/quality-check-cap.py`:
  - It counts only checks that surely ran.
  - Each check run records a working-tree fingerprint: HEAD, a hash of `git diff HEAD`, and the untracked file list. A repeat is denied only when no Edit or Write came after the run and the fingerprint is the same. If git fails after a fingerprint was recorded, the rerun passes. Outside a git repo, the old Edit and Write rule applies.
  - A formatter that writes is never denied, and it resets the cap.
  - A review-loop agent's gate run, a command that writes `/tmp/review-gate.log`, is never denied.
  - The deny text no longer suggests the skip marker. It tells the agent to stop and tell the user.
- New module `scripts/shell_command.py`, with its test.

## Evidence

Work incidents:
- After a `git merge --no-ff` changed 8 files, the cap denied `cargo test` with "nothing has been edited since". It blocked the full-suite gate after the merge in four work slices, and a clippy rerun in a fifth.
- The cap denied `cargo test` after real edits.
- The auto-mode classifier denied every command that carried the skip marker, so the review loop's gate run had no path through the cap.

## Result

Staged 2026-10-21 in the script fix batch. Installed 2026-10-21.

## Watch

None. The cap does not write to the hook block log that the watch metrics read.

## Back-out

Restore the previous `quality-check-cap.py` from the dotfiles history, and delete `shell_command.py` and its test.
