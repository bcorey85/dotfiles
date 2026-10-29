---
type: "Change"
change_type: "fixed"
title: "branch recap lists companion branches that have no PR"
description: "branch-recap gains a step that checks every other repo the spec names for a PR on its branch, lists a pushed branch with no PR first in a Companion branches section, and starts the Next line with opening it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:56:21-05:00"}
seq: 106
kind: "fix"
components: ["skill/branch-recap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_branch_recap_lists_companion_branches_that_have_no_pr"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New Step 2b: for each other repo the spec's phases or handover list name, `gh pr list --head <branch> --state all`.
  A pushed branch with no PR is listed under Companion branches, and the recap's Next line starts with opening it.
- The recap template gains the Companion branches section.

## Evidence

- A plan left a companion-repo merge to the user as a post-merge handover line. The main PR merged, and the
  companion branch sat pushed with no PR for four days; its code never went live. Nothing after the session
  pointed at it.
- The test pins the step and the section; it fails on the base tree.

## Result

- See the branch's suite run. The recap still opens no PR itself: it names the missing one where the user reads.

## Watch

—

## Back-out

Revert the commit.
