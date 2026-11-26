---
type: "Change"
change_type: "fixed"
title: "Permission-question gate counts tracker writes as outward"
description: "An ask to add, link, edit, comment on, label, assign or transition a tracker item counts as an outward step, so the Stop gate no longer forces a write to a shared tracker."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T14:16:43-06:00"}
seq: 5
kind: "fix"
components: ["script/permission-question-gate", "script/staged-claim-gate"]
evidence: ["queue: permission-question-gate-misses-an-ask-to-add-a"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest::test_a_question_about_a_tracker_write_passes_but_a_local_file_edit_is_sent_back"
asked: ""
proof: []
unmeasured: "A Stop-hook false positive with no logged rate; each hit pushed a session to write to a shared tracker unasked."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `gates/permission_question.py`: a new `OUTWARD_STEP` branch. A tracker verb (add, link, edit, comment, label, assign, transition) followed within two words by Jira, Linear, GitHub, GitLab, or a ticket, issue, PR, MR, pull or merge request counts as outward, when a clause end, `and`, `or`, a preposition (from, to, on, in, for, with) or `link from|between` follows the noun. A noun used as a modifier ("the ticket number", "the PR check") stays a local step. The file-name and GitHub-product guards apply. `commit message` no longer counts as an outward commit.

## Evidence

"Shall I add a Jira link from A to B?" was sent back as a reversible local step.

## Result

The new test fails before the change and passes after. Local file asks still block.

## Watch

None.

## Back-out

Revert the commit.
