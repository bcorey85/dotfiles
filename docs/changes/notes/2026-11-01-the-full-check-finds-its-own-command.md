---
type: "Change"
change_type: "fixed"
title: "The full check finds its own command"
description: "The review loop now runs a full check on repos with no CLAUDE.md line, so a repo no longer loses its suite for lack of one line, and a personal entry can name the command without touching the repo."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T19:15:23-06:00"}
seq: 455
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_repo_with_a_makefile_check_target_and_no_line_runs_make_check"
asked: ""
proof: []
unmeasured: ""
---

## Change

`full_check.py` resolves its command in order: an entry for the repo in `~/.claude/CLAUDE.local.md` (`Quality check (<repo name>): <cmd>`), the CLAUDE.md `Quality check:` line, then discovery from the repo's files: a Makefile `check` target, a package.json `check` script run by the lockfile's manager, then the lint, type and test parts. With nothing found, the result string stays the same and a note goes into the packet's `tool_fault`; it does not block. A repo marked `Full suite: CI` skips discovery. The started row names where the command came from.

## Evidence

Every finished review loop on three bench tickets and one more bench, over 32 loops, ran no full check, because those repos have no CLAUDE.md line. The user's rule is that personal workflow never forces a company repo to change, so adding the line was not an option.

## Result

The Makefile, local-entry and no-check tests fail on the old code and pass on the new. The full suite passes: 3034 tests, 0 failed.

## Watch

None. A discovered check that runs past 540 seconds reports `not run (timeout)` and the loop still converges with no repair coder. A local entry names a faster command for such a repo.

## Back-out

Revert the branch merge.
