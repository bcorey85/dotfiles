---
type: "Change"
change_type: "fixed"
title: "The fix brief names who changed an ask: the user or the session"
description: "A modified ask in the review-fix findings file now says who changed it. A ruling made with `asks-done --by session` no longer reads as the user's change."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T09:11:51-06:00"}
seq: 2
kind: "fix"
components: ["script/review-fix"]
evidence: ["fix-brief-says-the-user-ruled-when-a-session-did"]
watches: []
test: "tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_a_modified_ask_ruled_by_the_session_names_the_session_not_the_user"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_fix_asks.py` has a new `changed_in_place_sentence(decided_by, note)`. It compares the ruler against `plan_format.USER_RULING` and `plan_format.SESSION_RULING` and writes one of three sentences:
  - user: `The user changed it; make this change in its place: <note>` (the old words)
  - session: `The session changed it, not the user; make this change in its place: <note>`
  - no ruler in the state: `It was changed at the ruling; make this change in its place: <note>`
- `ask_deciders` stops with exit 2 on a saved ruler that is not `user`, `session` or null, and names `asks_decided_by` and the value. `asks-done --correct` calls it before it logs any row, so the correction stops with no row logged and no state saved.
- `ask_finding_text` takes the ruler and uses the sentence in both of its branches. `ask_finding_lines` and `accepted_finding_texts` take a required list with one ruler per ask.
- `asks-done` gives every ask the `--by` ruler. `asks-done --correct` reads each ask's ruler from the state (`ask_deciders`), so a session correction changes only the corrected ask.
- Help and usage text in `review_fix.py` and `review_fix_asks.py` say "the ruler's change" where a session can also make it. The `asks-done` line the script prints says `modified:<the change in one line>`.

## Evidence

Queue item `fix-brief-says-the-user-ruled-when-a-session-did`: `ask_finding_text` wrote "The user changed it" for every modified ask, also when `asks-done --by session` made the ruling. The coder that read the findings file took a session's change for the user's.

## Result

The named test fails on the old script and passes with the change. New `tests/scripts/test_review_fix_ask_ruler.py` has 16 tests: a user ruling and a session ruling; both branches of a converted ask; a `None` ruler and a state with no ruler field get the neutral sentence; an unknown ruler word and a ruler list shorter than the asks each stop `--correct` with exit 2; an unknown `--by` word is a usage error; notes with quotes, backticks, a newline and 20,000 characters; a session correction changes only the corrected ask; a session correction of a user-ruled ask says session; an accepted ask has no ruler sentence. The two stop tests also assert that the state file, the findings file and the ledger are unchanged. Run against the old scripts, 12 of the 16 fail; the other 4 assert the user sentence, the unknown `--by` usage error, or an accepted ask with no ruler sentence.

A session-ruled ask already went out as `--session-ruled N`, never `--user-ruled`. Phase asks do not use this text.

Not changed: `verify-log` `--asks-ruled` help says "the user's ruling", and `review_loop_prompts.py:54` (`user_ruled_issue`) names the user. Both sit outside this change's files.

## Watch

None. No intake number reads the ruler sentence.

## Back-out

Revert the commit. The findings file is rewritten on each `asks-done`, so it needs no cleanup. The session's ruled-impact rows keep the new sentence. After a revert, a finding ruled earlier in the same session does not match until a new session starts or the asks are ruled again.
