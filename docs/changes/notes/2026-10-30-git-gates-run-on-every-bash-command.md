---
type: "Change"
change_type: "changed"
title: "git gates run on every Bash command"
description: "The git discipline gate and the review commit gate lose their settings `if` filters, so a commit through a git alias or a command with no \"git\" text still reaches both gates, at about 50 ms per Bash call each."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T07:07:17-05:00"}
seq: 310
kind: "fix"
components: ["script/git-discipline-gate", "script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_hook_if_filters.py::HookIfFiltersTest::test_scripts_that_fire_per_command"
asked: ""
proof: []
unmeasured: ""
---

## Change

- settings.json: `git_discipline_gate.py` and `review_commit_gate.py` each have one PreToolUse(Bash) entry with no
  `if` filter, in place of two filtered entries each.
- The hook corpus test pins that `g commit -m x` fires both gates and that neither carries a filter.

## Evidence

The `if` filters skipped both gates for any command without "git" (or "gh", "review-gate-mark") in its text, such as a
git alias. Nothing tested what the filters let through.

## Result

Targeted tests pass. Each gate run through `hook-python` on a plain `ls -la` hook event, 30 runs each, on this
machine:

- git discipline gate: median 46.2 ms, p90 49.8 ms (43.9 to 51.7 ms).
- review commit gate: median 49.8 ms, p90 54.3 ms (46.3 to 55.3 ms).

Both exit 0 with no output, so a non-git command costs about 96 ms more wall-clock per Bash call when the hooks run
one after another, and no tokens.

## Watch

None; a fix with no intake number.

## Back-out

Restore the four filtered entries in settings.json and the old expected filters in the test.
