---
type: "Change"
change_type: "fixed"
title: "comment-bloat gate lets agent-evals and shell code name plan impacts and acceptance criteria"
description: "The plan-impact and acceptance-criteria markers no longer fire in an agent-evals checkout or on a shell line that is not a comment. A comment in any other repo still blocks."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T21:33:28-05:00"}
seq: 417
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_domain_words_in_an_agent_evals_file_pass_but_other_markers_block"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `comment_bloat_gate.py` moves `acceptance criteri` and `plan[ -]?impact` out of the general markers into
  `EVAL_DOMAIN_MARKERS`.
- Those two count only when the file is outside an `agent-evals` checkout (`agent-evals/` or `agent-evals-<name>/`)
  and the line is a comment or the file is not a shell script.
- Every other marker, and both words in a work-repo comment, docstring or test name, still block.

## Evidence

- Queue item `comment-bloat-gate-blocks-plan-impact-names-in`: the gate fired three times on an agent-evals intake
  script, on docstring lines, a test class name and a non-comment shell step `run plan-impacts ...`. There the words
  are the domain.
- The two new tests fail on the base commit (7 failures) and pass after.

## Result

- `test_comment_bloat_gate` passes (46 tests); ruff check passes.

## Watch

—

## Back-out

Revert the commit.
