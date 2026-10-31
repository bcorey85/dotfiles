---
type: "Change"
change_type: "fixed"
title: "A planless /code run edits the plan docs an adopt needs and says it is not committed"
description: "After `decide adopt` in a planless run, code-step dispatches a coder to rewrite the branch's plan docs and add a Plan Deviations entry, and the review then covers that edit; the planless end says nothing is committed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T12:00:00-05:00"}
seq: 154
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_planless_adopt_dispatches_a_coder_for_the_plan_docs_then_reviews_and_commits_its_edit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `decide adopt` in a planless run dispatches a plan-edit coder, as a planned run does. The coder finds the branch's
  plan docs that state the overturned side, rewrites the contradicted lines and adds a `## Plan Deviations` entry. It
  edits no code, test or acceptance criteria file; a criterion change comes back as an OPEN CHOICE.
- `after-plan-edit` in a planless run adds the edited plan docs to the review's files, flags any other file the coder
  changed, and dispatches the review. The plan docs then land in the planless commit command.
- The planless end's stop line says `Nothing is committed: run the commit command above.` when there is one.

## Evidence

- A planless run ended with "Planless task reviewed" after a session `decide adopt`. The plan-doc rewrite, the Plan
  Deviations entry and the commit were left to the parent session, outside /code and unreviewed.
- The new tests fail on the old scripts.

## Result

- An adopted ruling in a planless run reaches the plan docs through a reviewed coder, and the caller is told to commit.

## Watch

—

## Back-out

Revert the commit.
