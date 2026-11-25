---
type: "Change"
change_type: "changed"
title: "Reviewer dispatch lines name their round and role"
description: "Reviewer dispatch output groups lines under `round <n>: dispatch these <k> reviewer(s) now`, each line reads `- round <n>: <role>; agent ...`, and a later round's lines print from the same `code_wait.py review` call."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T19:31:31-06:00"}
seq: 5
kind: "fix"
components: ["skill/code", "script/code-step"]
evidence: ["tests/scripts/test_code_wait.py", "tests/scripts/test_reviewer_dispatch.py"]
watches: []
test: "tests/scripts/test_code_wait.py::ReviewerRequestTest::test_a_round_two_request_written_after_round_one_prints_from_the_same_wait_call"
asked: ""
proof: []
unmeasured: "No rule-meter fixture holds a round-two reviewer request: the skill sentences only name the line shape the script prints, and the script tests pin the shape and the same-call print."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/reviewer_dispatch.py` prints each round's lines under a `round <n>:` heading, one `- round <n>: <role>; agent ...` line per reviewer. An old manifest with no round on its entries takes the manifest's round; a manifest whose `round` is not a whole number stops with an error. `code/SKILL.md` step 5 and `_shared/review-fork-run.md` `## Reviewers` dispatch a later round's lines as new agents from the same wait call.

## Evidence

`test_code_wait.py` and `test_reviewer_dispatch.py` pin the labels, the old-manifest default and the same-call round-two print.

## Result

Before, a round-two dispatch line did not say its round or role, so the fork could not tell it from a round-one line.

## Watch

—

## Back-out

Revert the commit.
