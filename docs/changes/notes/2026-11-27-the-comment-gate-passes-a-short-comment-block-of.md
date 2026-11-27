---
type: "Change"
change_type: "changed"
title: "The comment gate passes a short comment block of at most two lines"
description: "comment-bloat-gate still keeps its four kinds, and also passes a run of at most two added comment lines that are no kept kind; a run of three or more is blocked with a message that sends architecture prose to the repo's architecture docs and names coder-core."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T12:11:48-06:00"}
seq: 3
kind: "user-rule"
components: ["script/comment-bloat-gate"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-27: asked by the user"
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The gate blocked every added comment line that was no kept kind. It now groups the added non-kept lines into runs and passes a run of one or two lines. A run of three or more is blocked; the deny says architecture goes in the repo's architecture docs, never in code comments, and names `skills/coder-core/SKILL.md`. Old lines inside a run do not count and do not split it; blank, suppression, directive and URL lines bridge a run without counting; a license header or a public-symbol doc line ends it; a blank line ends a `#` paragraph. The gate applies in every repo and writes nothing into any repo.

## Evidence

user request: one comment rule in every repo, with short comments allowed. `tests/scripts/test_comment_bloat_gate.py::CommentBloatGateTest::test_a_non_kept_comment_block_of_one_or_two_lines_passes_and_of_three_blocks` pins 1, 2 and 3 line blocks.

## Result

—

## Watch

—

## Back-out

Restore `comment_bloat_gate.py` from the commit before this change.
