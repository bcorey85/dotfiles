---
type: "Change"
change_type: "changed"
title: "Code runs end phases on a statement, decide review asks and relay the stop word for word"
description: "The /code fork asks no leave for a reversible step, ends every phase stop on a statement, and rules on review asks itself. The main session relays the fork's stop through `code_relay.py` and makes no other tool call before the user replies."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:04:45-06:00"}
seq: 421
kind: "user-rule"
components: ["skill/code", "agent/code-fork", "script/code-relay"]
evidence: ["judgment"]
watches: ["code-no-asks-main-cache-read"]
test: ""
asked: "2026-11-01: on permission questions in /code runs, \"I FUCKING HATE THESE, 90% of the time the questions are pointless\"; on the main session's checks after a hand-back: \"why is main checking what has just been through code AND review loop cycles?\"; on auto-advancing phases: \"no. i need phases so i can review and stage.\""
proof: []
unmeasured: ""
overlap: "The watch code-plain-steps-main-cache-read reads the same metric for /code turns and expects it flat; this edit expects it down, so read both against the same before-window. The Stop hook that sends back a turn ending on a reversible-step question (queue item ship-the-stop-hook-that-sends-back-a-closing) covers main-session asks outside /code and also lowers main replies per turn."
---

## Change

The /code skill tells its fork that the next phase, a coder dispatch, a commit, a write and a confirmation are reversible, so it never stops to ask leave for them. When two paths are both defensible, it takes the one closer to the plan and names it. Every stop states what stopped and what the user does next, and never ends on a question. Phase stops stay where they were: the user reviews and stages there.

A review packet's asks no longer stop the run. The fork accepts an ask whose change fixes a defect inside the phase's scope and changes no acceptance criterion, sends an ask that changes a criterion to the plan changes awaiting sign-off, and rejects the rest. It logs each ruling with `ask_decided_by=session` and lists it under `Asks decided` in the phase block.

The skill description, which the main session reads, says to run `scripts/code/code_relay.py` when the fork hands back. The script prints `<run folder>/stop.md` between USER TEXT markers under the rule: say it word for word, make no other tool call, send fixes back through `/code resume`. A stop that was relayed already, or a missing stop file, exits 1 and says to relay the Skill result instead.

## Evidence

The intake from 10-29 counts 132 /code runs since 10-19. Of their 85 questions, 56 asked leave for a reversible step. The main session's re-check replies after a hand-back hold 11.6 percent of main Opus cache read on /code runs, and its own reports, which rewrite the fork's text, hold 10.4 percent.

## Result

Tests: `tests/scripts/test_code_relay.py` (relay word for word, a second relay refused, a rewritten stop relayed, no stop file) and `tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_code_stops_end_as_statements_asks_are_decided_and_main_relays_with_no_tool_call`.

## Watch

`code-no-asks-main-cache-read`: main-session Opus cache read per /code turn, expected down.

## Back-out

Revert the commit.
