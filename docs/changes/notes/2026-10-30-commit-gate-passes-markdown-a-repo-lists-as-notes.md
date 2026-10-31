---
type: "Change"
change_type: "fixed"
title: "Commit gate passes Markdown a repo lists as notes"
description: "The commit gate passes a Markdown-only commit once its repo commits a list of note paths; a repo with no list is denied as before."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T11:17:03-05:00"}
seq: 343
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::NotesOnlyCommitTest"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/scripts/review/review_commit_gate.py`: the notes rule also passes Markdown under a path listed in the repo's `.claude/notes-paths`. An entry ending in `/` is a folder and any other entry is one file.
- The gate reads the list from HEAD, so an uncommitted or staged edit grants nothing. Every path must still end in `.md`, and the list file itself is never a note.
- The deny text names the list. An entry that is not a normalized repo-relative literal denies the commit and names its line; `review_commit_gate.py check <file>` prints the same errors.

## Evidence

A queue release waited on the user and a queue close waited on an unrelated dashboard review. Every queue write in a session with unreviewed work hit the same deny.

agent-evals commits its own `.claude/notes-paths` listing `queue/`, `QUEUE.md`, `findings/` and `proposals/`.

## Result

The new tests that pass a listed note fail on the old gate and pass on the new one. The gate's test file passes.

## Watch

None. No intake number reads a queue commit's deny.

## Back-out

Revert the commit. The notes rule returns to `docs/` alone.
