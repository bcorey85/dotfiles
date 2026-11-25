---
type: "Change"
change_type: "changed"
title: "A code resume that changed source gets a review before its stop"
description: "A /code resume that changed source and writes stop.md with no review loop started in the run is denied once, and the deny names the changed files."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T11:23:45-06:00"}
seq: 1
kind: "fix"
components: ["skill/code", "script/code-step", "script/gate"]
evidence: ["tests/scripts/test_fork_write_scope.py", "tests/scripts/test_phase_start.py", "tests/scripts/test_code_skill_text.py"]
watches: []
test: "tests/scripts/test_fork_write_scope.py::ResumeReviewTest::test_a_source_edit_with_no_review_loop_is_denied_naming_the_file"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`code/phase_start.py --resume` writes `<run folder>/resume.json` with the repo, HEAD and tree fingerprint. The new `code/resume_review_gate.py` compares the tree at the code-fork's Write of `stop.md` against that record. `gates/fork_write_scope.py` denies the Write once when source changed (edited, deleted, committed or new untracked) and no review loop started in the run, and names the changed files. Notes paths do not count. A missing record passes; an unreadable record exits 2 naming the gate. `code/SKILL.md` Resume says a resume whose feedback changes files runs `phase_start.py --resume` before its coder and the review before any stop, unless the diff is empty.

## Evidence

`test_fork_write_scope.py` pins the deny for an edit, a delete, a commit and a new file, and the allow for a started loop, a notes-only change, a second Write, no record and a non-fork agent. The hook event fixture is `tests/scripts/fixtures/hook_event_code_fork_write_stop.json`.

## Result

Before, a /code resume could apply a fix list and write its stop with no review of the changed source.

## Watch

—

## Back-out

Revert the commit.
