# Design Decisions — stop-hook-gate-1127

> Research: ./02-research.md
> Status: 7/7 resolved

## Queue

- [x] D1. Which gated shapes the announced-step check adds — from backend-architect
- [x] D2. Where the new vocabulary lives — from backend-architect
- [x] D3. What `systemMessage` holds — from backend-architect
- [x] D4. Whether SubagentStop blocks also get `systemMessage` — from backend-architect
- [x] D5. The helper's shape — from backend-architect
- [x] D6. Dates already past — from spec-criteria
- [x] D7. A block with an empty reply — from spec-criteria

## Resolved

### 1. Gated shapes added to the announced-step check

- **Choice:** A sentence is no announcement when it also holds (a) a date or clock gate: `on|by <weekday>`, `on|by <month> <day>`, `at H:MM` or `at :MM`, `tomorrow`, `tonight`, `the next time`; (b) a later event: `later <noun>` ("later merges", "later lanes"); (c) a wait on another party's notice or result: `act on (its|their|the) ... (notice|result|report)s?` ("act on their completion notices"); (d) a chained step: a sentence opening on `Then`, `Next` or `After that` passes when the sentence before it is gated (condition, other actor, work runs, or one of a-c). The ticket's three example forms get regression tests; they already pass through `CONDITION`.
- **Reasoning:** agent-evals-74 approved the lane session's picks on 2026-11-27, and asked that the change file say own-step ordering still blocks. Each form appears in the real sweep of 139 flagged sentences (`flagged.json`): chained steps are 32 of the 37 Then/Next/After-that sentences, "at :47" and "the next time" are clock forms, and "later merges" and "act on their completion notices" are real blocked replies. "on Nov 29" is the ticket's date class written with `on`, and it fails today.
- **Alternatives rejected:** bare `on`, `at`, `before` or `later` added to `CONDITION`, which would let "I'll work on it" and "I'll look at X" pass; a whole reply passing on a "Your turn:" or "Waiting on:" heading, which would let a bare promise elsewhere in that reply pass (breaks AC 2); a date-parsing package, which adds a dependency and startup cost on every Stop.
- **Trade-off accepted:** own-step timing ("at the end", "before starting", "in my final report") keeps blocking, so real blocks 1-3 from 2026-11-27 still block. Fix 1 shows those replies to the user.

### 2. Where the vocabulary lives

- **Choice:** new module constants in `gates/announced_step.py` (`TIME_GATE`, `LATER_EVENT`, `OTHER_PARTY_RESULT`, `CHAINED_STEP`), checked beside `CONDITION`; the docstring lists each.
- **Reasoning:** the vocabulary is that module's own rule, and its docstring lists the pass forms by kind.
- **Alternatives rejected:** widening `CONDITION`, which mixes kinds and hides which form passed a sentence.
- **Trade-off accepted:** the sentence loop remembers whether the previous sentence was gated, one more state variable.

### 3. What `systemMessage` holds

- **Choice:** a label line, then a blank line, then the reply text. Over the documented 10,000-character cap, the text is cut so the whole message fits, and it ends with a line saying it was cut.
- **Reasoning:** agent-evals-74 approved the lane session's pick on 2026-11-27. Without the label, the user sees the reply twice with no reason. The docs cap the field at 10,000 characters (https://code.claude.com/docs/en/hooks#json-output); the sweep's largest blocked reply is 2,337 characters, so the cut is rare.
- **Alternatives rejected:** the bare text, which shows a duplicate reply with no source.
- **Trade-off accepted:** a reply over the cap shows cut.

### 4. SubagentStop

- **Choice:** `systemMessage` on Stop blocks only.
- **Reasoning:** agent-evals-74 approved the lane session's pick on 2026-11-27. A subagent's reply goes to its caller, not to the user, so a block hides nothing from the user. Putting a subagent's text in the user's pane would add noise.
- **Alternatives rejected:** both events, which shows every blocked subagent reply in the user's pane.
- **Trade-off accepted:** the brief's wording "every Stop hook that can block" is read as the Stop event.

### 5. Helper shape

- **Choice:** `lib/stop_block.py` with `block_line(reasons, reply, show_reply) -> str | None`: the JSON line for the hook to print, or None when no reason holds. `show_reply` adds the `systemMessage`.
- **Reasoning:** plain strings in, JSON out, no gate knowledge, so it belongs in lib/. The gate keeps one print.
- **Alternatives rejected:** a dict returned for each gate to dump, which leaves JSON encoding to each caller.
- **Trade-off accepted:** none.

### 6. Dates already past

- **Choice:** a date gate passes on its words alone; the gate never checks whether the date has gone by.
- **Reasoning:** agent-evals-74 approved the lane session's pick on 2026-11-27. The gate has no clock it can trust for the wait, and a stale date in a closing reply is rare.
- **Alternatives rejected:** parse the date and block once it has passed, which needs a date parser and the year.
- **Trade-off accepted:** a reply that names a past date passes.

### 7. A block with an empty reply

- **Choice:** no `systemMessage` key when the reply is empty.
- **Reasoning:** agent-evals-74 approved the lane session's pick on 2026-11-27. An empty warning shows the user nothing useful.
- **Alternatives rejected:** a placeholder line.
- **Trade-off accepted:** none.

### AC12 ruling

- **Choice:** AC12 (the live pane check) stays open past merge. agent-evals-74 checks the pane at the first Stop block after the user merges v2.
- **Ruled by:** agent-evals-74, 2026-11-27.

### Negated announcements and blocks 1-3

- **Choice:** an allow list. A sentence whose every first-person announcement is negated in an allowed form passes: at most one start word then `no`, `nothing` or `none`, not followed by an idiom word (`but`, `other`, `more`, `short` and the like); or `not` then a start word or `act`. Every other negation blocks, and a clause joined after it blocks. A negated sentence opens no Then or Next chain. Blocks 1-3 stay blocked under D1. A review finding that names another idiom blocks under the allow list and is ruled no-change.
- **Ruled by:** agent-evals-74, 2026-11-27, after the gate blocked "I'm starting no lane for it." in a reply whose steps all waited on another session; the allow list replaced a 30-word exclusion list the same day.

## Direction & Constraints

- Only `gates/staged_claim_gate.py` can block among the Stop and SubagentStop hooks: `format_changed.py` prints no decision on Stop and always exits 0, and `ledger-hook` runs async, which the hooks docs say cannot block (https://code.claude.com/docs/en/hooks#run-hooks-in-the-background). Fix 1 touches that one gate plus a new lib helper.
- Docs facts (https://code.claude.com/docs/en/hooks#json-output, #stop-decision-control): `systemMessage` is a warning shown to the user, capped at 10,000 characters per field; Stop decision control is `decision: "block"` plus a required `reason`. The docs do not say that Stop discards `systemMessage`.
- Real input sweep (lane session, 2026-11-27): the orchestrator transcript of 2026-11-27 holds 4 announced-step blocks (`real_blocks.json`). The sentences flagged were: "I'll check who holds them before starting any of them.", "I'll list it under Questions in `questions-for-dev.md`.", "- One merge line, which I'll write up at the end.", "I'll send later merges to `weekend-toolkit-fixes-v2`." All 21,321 transcripts on this machine give 139 distinct flagged sentences (`flagged.json`).
- The queue item's three example forms ("once X confirms", "after Nov 29", "when the lane reports") already pass today through `announced_step.CONDITION`, so the fix change file cites a new shape that fails before ("on Nov 29", "at :47") as its test. The examples get regression tests.
- Hook timing is measured with a scratchpad loop, not a repo harness: baseline on be9a5807d is bare Python 8.1 ms, staged_claim_gate.py 43.6 ms (21 runs, median).
