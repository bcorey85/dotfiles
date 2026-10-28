---
type: "Change"
title: "The comment-bloat gate finds plan paths and provenance inside strings"
description: "The `docs/plans/`, `per the <source>` and `written by the <author>` markers search the raw line again, so an error or log string that names one blocks; the phase, AC and other markers still skip string text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:00:00-05:00"}
seq: 163
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_a_plan_path_or_provenance_in_a_shipped_string_blocks_but_a_phase_fixture_string_passes"
asked: "2026-10-28: agent-evals-64 assigned queue item comment-bloat-gate-skips-plan-paths-and-provenance"
proof: []
unmeasured: ""
---

## Change

- New `RAW_LINE_MARKERS` holds the plan-path and provenance patterns. They search the raw line, string text included.
- The other markers still search the line with string text removed, so a `## Phase 1` fixture string passes.
- Lines inside a multi-line data string are still skipped. On a line that opens or closes one, the raw search covers
  only the code part, as before.

## Evidence

- A review pass found that a `docs/plans/` path or "per the spec" inside a shipped error string passed the gate.
- The new test fails on the old gate for all four strings.

## Result

- An added code line that names a plan path or a provenance source in a string blocks. A test that builds such a path
  in a one-line string now needs the path split, as test_comment_bloat_gate.py already does.

## Watch

—

## Back-out

Revert the commit.
