---
type: "Change"
change_type: "fixed"
title: "a review-loop coder edit to a CLAUDE.md file becomes an ask for the user"
description: "A fix coder that changes a file named CLAUDE.md, CLAUDE.local.md or AGENTS.md, unless a finding the user ruled on names it, or a session ruled on the approval ask itself, leaves an open ask in the packet, so the edit never rides out as a silent fix."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T12:34:40-06:00"}
seq: 6
kind: "fix"
components: ["script/review-loop"]
evidence: ["review-loop-coder-edits-claude-md-without-approval"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_coder_edit_to_a_claude_md_file_reaches_the_packet_as_an_ask_for_the_user"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_loop_ruled.py` `ask_for_approval_only_edits` files one ask per changed file whose basename is `CLAUDE.md`, `CLAUDE.local.md` or `AGENTS.md` (`PROMPT_MARKDOWN_NAMES` in `lib/format_files.py`), under the `coder` gate name. `review/review_loop_script.py` `repair` calls it after every coder pass, also when the coder call fails. The ask rides the packet's existing `ask` list, so `handback.py` and the commit gate treat it like any open ask. A file named by a finding the user ruled on files no new ask. A session ruling counts only on the approval ask itself (its revert). The run's status is unchanged. No prompt text changes.

## Evidence

Queue item `review-loop-coder-edits-claude-md-without-approval`: a fix coder widened an Owners line in a scripts `CLAUDE.md`; the lane session caught it by reading the last-fix diff.

## Result

The named test fails on the old scripts (the packet holds no ask) and passes with the change. A second test pins that `NOT_CLAUDE.md` files no ask.

## Watch

None. No intake number reads this.

## Back-out

Revert the commit.
