---
type: "Change"
change_type: "changed"
title: "inline-interpreter deny names the session scratchpad first"
description: "The inline-interpreter deny text opens with the route to a script file and names the session's scratchpad folder when it exists; otherwise it keeps the general words."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T18:20:00-06:00"}
seq: 5
kind: "fix"
components: ["script/inline-interpreter-hint", "script/hook-input"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_inline_interpreter_hint.py::InlineInterpreterHintTest::test_the_deny_leads_with_the_route_and_names_the_existing_session_scratchpad"
asked: ""
proof: []
unmeasured: "The drop in repeated inline-interpreter denies per session: the replay is not run under this load and is queued separately."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`inline_interpreter_hint.py` builds its deny text with the route first. `hook_input.existing_session_scratchpad`
returns `<claude code temp root>/<transcript folder>/<session id>/scratchpad` when the payload names one that exists, and
the route names that folder; with none, the route says "your scratchpad directory".

## Evidence

Judgment: one session hit 27 inline-interpreter denies; each deny opened with what is blocked and named the scratchpad
only in general words. The route-first test failed before the change.

## Result

A denied session reads the exact folder to write the script to in the first words of the deny.

## Watch

None.

## Back-out

Revert the commit: the deny opens with what is blocked again.
