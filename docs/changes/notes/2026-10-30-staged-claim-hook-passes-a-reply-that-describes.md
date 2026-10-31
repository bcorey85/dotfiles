---
type: "Change"
change_type: "fixed"
title: "Staged-claim hook passes a reply that describes what it reads"
description: "The staged-claim Stop hook no longer blocks a reply that reports speech, such as \"a reply that says files are staged\", so a session can describe the hook without a false refusal. The subdirectory test now runs the passing path it names, and git_calls.py has its reading rules back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T13:28:03-05:00"}
seq: 403
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::StagedClaimGateTest::test_a_reply_describing_what_the_hook_reads_passes_with_an_empty_index"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/scripts/gates/staged_claim_gate.py`: `is_index_claim` drops a claim whose clause holds `REPORTED_SPEECH` (`say`, `said`, `claim` and their inflections, as a word of their own). `I staged` stays a claim, and the name `staged-claim` is not read as speech.
- `tests/scripts/test_staged_claim_gate.py`: the subdirectory test stages `sub/c.txt` in the linked tree and asserts the pass. The old block moved to a test named for what it does.
- `claude/.claude/scripts/lib/git_calls.py`: the docstring carries the sentence on heredoc bodies, comments and quoted strings again, and the unreadable-path comment sits on `UNREAD_PATH_MARKS`.
- Limit: a claim worded as third-party speech ("the log says the files are staged") passes.

## Evidence

- The hook blocked a reply that only described the staged-claim bug. The other two items were left open at the end of review of the worktree-index change.

## Result

- The five description messages block on the base gate and pass on the new one. All 34 tests in the file pass, and `ruff check` passes.

## Watch

—

## Back-out

Revert the commit. A reply that describes the hook is blocked again.
