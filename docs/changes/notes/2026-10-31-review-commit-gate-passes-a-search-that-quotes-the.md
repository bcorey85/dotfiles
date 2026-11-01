---
type: "Change"
change_type: "fixed"
title: "review-commit-gate passes a search that quotes the commit words through a text tool, cd or loop"
description: "A log search that quotes the commit words runs in a dirty session when it pipes through sort, uniq, cut or jq, follows a cd or ls, or sits in a for or if: review-commit-gate reads those steps as probes, so the search needs no rewording. A real commit in any of those shapes is still denied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T20:43:35-05:00"}
seq: 411
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_a_search_that_quotes_the_commit_words_through_a_text_tool_cd_or_loop_passes_while_dirty"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The probe list, whose steps never count as a commit by their text alone, adds cut, uniq, tr, nl, column, jq,
  sort, ls, cd, pwd and true. sort with `--compress-program` or any shortened form is no probe, since it runs that
  program, the same rule rg already had for `--pre` and `--hostname-bin`.
- A leading shell keyword (do, then, else, elif, if, while, until, `!`, `{`) is skipped and the rest of the step
  judged. A `for` header and a bare done, fi or `}` run nothing.
- The text match stays fail-closed for any other program, so an interpreter or shell runner that holds the words is
  still denied.

## Evidence

judgment: the gate denied a read-only search of a session log for the commit words, and the queue call that
reported it, on one day. Plain `grep` and `git log --grep` already passed; the same search piped through a text
tool, after a `cd`, or in a loop did not.

## Result

The named test fails before (all nine shapes denied) and passes after. A companion test keeps a real commit denied
after a `cd`, inside a for, if or `!`, in a `for` list substitution, and after `sort --compress-program`.
`test_review_commit_gate`: 128 tests, 0 failed; ruff clean.

## Watch

None. A wrong deny shows in the session that hits it.

## Back-out

Revert the probe list, `PROGRAM_RUNNING_OPTIONS`, the keyword lists and their use in `is_safe_probe`, and the two
tests.
