---
type: "Change"
change_type: "fixed"
title: "Stale-prose check ignores moved symbols, and a hit after a fix goes to a coder"
description: "The stale-prose check no longer lists prose for a symbol that only moved, and in the review loop a hit (exit 1) goes to one coder pass instead of stopping as critical-blocker."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T09:40:35-05:00"}
seq: 351
kind: "fix"
components: ["script/code-step", "script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_stale_prose.py::StaleProseTest::test_a_symbol_moved_with_its_doc_line_lists_no_prose"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `stale_prose.py` counts a declaring hunk side as moved when its stripped non-blank lines appear in order, with no
  line between them, on the other side of one hunk, and its hunk does not declare different names on its two sides.
  A symbol that only moved has no label. One that moved and took a new, dropped or reordered line stays `changed`.
- A hunk header counts as unchanged only when both sides of the hunk only moved and the first declaring line of each
  side sits at or above the header's indent. A whole moved symbol drops the header; a declaration reordered inside
  the header symbol's body starts deeper and keeps the `body changed` hit.
- The review loop's scoped tests no longer run the stale-prose gate command as a test. After they pass, the loop runs
  it on its own. Only an exit 1 (a hit) goes to one coder pass. Any other failing exit stops the loop as
  `critical-blocker`; a timeout, setup fault or command error joins the packet's `scoped_tests` line.
- After a prose repair that changed a file, the loop runs the full check, and reruns the scoped tests when the full
  check left the fix untested. A red one stops the loop.
- `coder_gate.is_stale_prose_check` matches a command word whose file name is the script's, so a test file named
  `test_stale_prose.py` stays a test.

## Evidence

A pure move of a documented function listed prose that names it, though nothing about it changed. A stale-prose hit
after a fix stopped the loop as `critical-blocker` and no coder pass read the prose.

## Result

Targeted tests pass: a moved symbol with its doc line lists no prose, an edited, resized or reordered moved symbol
stays changed, two functions that swap names keep their hits, a hit goes to a coder, and an exit-2 command stops the
loop.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
