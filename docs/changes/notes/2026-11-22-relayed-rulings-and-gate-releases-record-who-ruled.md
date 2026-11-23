---
type: "Change"
change_type: "changed"
title: "Relayed rulings and gate releases record who ruled and when, never the user's words"
description: "A relayed user ruling is `--by user --relayed-by <session name>` with no words: the script checks that the relaying session's transcript holds a typed user turn after the ask and stores only that turn's time; `--quote` is refused, the standing ruling line holds a short paraphrase with no quote marks, and the prompts that asked for the user's words verbatim now ask for the outcome, who gave it and when."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T20:47:10-06:00"}
seq: 37
kind: "user-rule"
components: ["script/ruling-relay", "script/review-fix", "script/review-fix-asks", "script/phase-asks", "script/handback-store", "script/plan-format", "script/coder-packet", "shared/review-fork-run", "skill/code", "agent/code-fork", "rule/orchestration"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: asked that the toolkit stop storing the user's words"
proof: []
unmeasured: "RF06 meters the review-fork relay line. The orchestration relay rule, the code-fork gate release and the /code gate-release wording have no scenario that tells a paraphrase from a quote."
---

## Change

- `review/ruling_relay.py`, `lib/human_turn_lookup.py`, `lib/ask_outcome_words.py`: a relay takes `--relayed-by
  <session name>` alone. The lookup returns the latest typed user turn of that live session after the ask or impact
  was filed, and refuses when there is none. `--quote` is refused with a pointer to the new form.
- `review/handback_store.py`: relayed-ruling rows keep the ruler, the relaying session and the turn's time; the
  `quote` field is gone. `review/review_fix_plan_impacts.py` writes `relayed by session <name> (user turn at
  <time>)` into the plan line in place of the words.
- `lib/standing_rulings.py`: `Standing ruling by <who> at <YYYY-MM-DD>: <a short paraphrase> covers: rewords`; a
  paraphrase with quote marks fails the grammar. The parsed key is `summary`.
- `lib/plan_format.py` `DECIDE_BY_NOTE`: `--ruling` states the decision in the session's own words, never the
  user's.
- `code/coder_packet.py`: the `--gate-evidence` placeholder asks for what was released, in the caller's words.
- Prompts: `orchestration.md` (send the user's ruling: outcome, that the user gave it, the date, never the words),
  `agents/code-fork.md` and `skills/code/SKILL.md` (a gate release names sender, date and what it released),
  `skills/_shared/review-fork-run.md` (the relay line is `ruled by: user, relayed by <session name>`),
  `docs/glossary.md` (relayed ruling).

## Evidence

- user request: the user asked that the toolkit stop storing their words.

## Result

- Rule meter RF06 (the review-fork relay line, sonnet): with the rule 8 of 8 runs passed `--by user --relayed-by`
  with no `--quote`; without it 0 of 9 did, at each prompt level.
- 1,137 tests in the 10 changed relay, plan and hand-back test files pass; lint passes on the changed scripts.
- Full suite: 5,667 tests in 190 files, 0 failed; lint passes.

## Watch

None in the intake: see `unmeasured`.

## Back-out

Revert the commit. No stored row or plan line needs migrating: no real plan holds a standing ruling line, and old
relayed-ruling rows with a `quote` field are read by nothing.
