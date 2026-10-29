---
type: "Change"
title: "comment-bloat gate skips files git ignores"
description: "The write-time comment-bloat gate no longer checks files git ignores, so a scratch probe script that names a plan path in a string is not blocked."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T16:33:39-05:00"}
seq: 279
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_a_file_git_ignores_passes_but_a_tracked_file_matching_an_ignore_pattern_is_still_flagged"
asked: ""
proof: []
unmeasured: "A block on a file that is never committed leaks nothing, so no intake count reads the gain."
---

## Change

When a write would otherwise block, the gate asks `git check-ignore` about the file's resolved path (symlinks followed), from the nearest folder that exists, with a 2 s timeout, and exits 0 when git ignores it. The shell-write gate now follows symlinks and times out the same way. A tracked file is never reported as ignored, so it is still checked even when a `.gitignore` pattern matches it. A file outside a repo, a missing git, a timeout or a git error leave the gate checking the file as before. The check is a shared helper, `is_git_ignored`, in the script utilities; the shell-write gate's own copy of that check is removed and it calls the shared helper.

## Evidence

judgment

## Result

A Write to a gitignored scratch script with a plan path in a string literal passes. The same content in a tracked file that matches an ignore pattern still blocks.

## Watch

None.

## Back-out

Remove the `is_git_ignored` call from the comment-bloat gate. To restore the shell-write gate's own copy, revert its change in `shell_write_gate.py`.
