---
type: "Change"
title: "A phase commit subject names its phase"
description: "A plan run's commit subject built from the coder summary or the title ends with (phase <id>), or (plan <folder>) with no phase; a plan-named Commit line and planless runs are unchanged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:00:00-05:00"}
seq: 187
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_commit_subject.py::CommitSubject::test_a_phase_without_a_commit_line_uses_the_coder_summary_and_names_the_phase"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_boundary.py` `commit_message`: with no plan-named Commit line, a plan run's subject gets " (phase <id>)",
  or " (plan <folder>)" when the run has no phase. A subject that already names the phase gets nothing.

## Evidence

- Queue item code-review-lists-findings-on-files-absent-from: the commit message did not name the spec phase.
- The new tests fail on the old script.

## Result

- `git log` shows which plan phase each commit closed.

## Watch

—

## Back-out

Revert the commit.
