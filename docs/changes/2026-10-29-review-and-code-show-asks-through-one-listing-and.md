---
type: "Change"
change_type: "changed"
title: "review and code show asks through one listing and jump helper"
description: "/review and /code list asks and jump the editor to them through one set of helpers in review_asks.py, so the two copies that had drifted apart become one."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T19:38:33-05:00"}
seq: 290
kind: "fix"
components: ["script/review-fix", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_asks.py::AskListingAndJump::test_jump_anchor_args_keep_only_one_well_formed_anchor_per_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_asks.py` gains `jump_anchor_args`, `run_nvim_jump` and `numbered_ask_lines(asks, detail=...)`. `review_fix.py` drops its `run_nvim_jump` and `ask_listing_lines`; `code_step_review.py` drops its anchor loop and `code_step_asks.py` drops its `numbered_ask_lines`. Each side still reads its own nvim-jump command variable. `test_code_step_termination.py` now patches `run_command` on `review_asks`, where the /code jump runs.

Differences settled:

- Jump anchors: /review passed every file_line (a list cut to its first location, or a bare path); /code passed only one `path:line(-line)`. Both now pass only one well-formed `path:line(-line)`. No test pinned either rule. The old /review path went through split_location/normalize_path, so (a) a line range `src/a.ts:3-9` was sent as `src/a.ts:3` and is now sent as `src/a.ts:3-9`; (b) backticks or quotes around an anchor were stripped, so an anchor wrapped in backticks used to jump and now does not (JUMP_ANCHOR rejects it); (c) a leading `./` was removed and is now passed through unchanged; (d) the `unlocated` sentinel, once sent as a bare path, is now dropped. Packets built by the loop carry plain path:int, so only hand-written or plain-text packets differ.
- Jump note: /review used the question collapsed to one line, cut at 160 characters; /code cut the raw question at 120, newlines kept. Both use the /review rule. No test pinned either rule.
- Not installed: /review read exit 2 or 127 and printed that nvim-jump is not installed; /code checked `shutil.which` and said nothing. Both check `shutil.which` first and still read exit 2 or 127, so /review now catches a missing nvim-jump before it runs it, with the same message. The /review message is kept, pinned by `test_review_fix_script.py::ReviewFixScriptTest::test_missing_nvim_jump_does_not_stop_the_run`.
- Status line: only /review prints one; unchanged, pinned by `test_review_fix_script.py::ReviewFixScriptTest::test_nvim_jump_with_no_owner_is_silent_and_still_lists_the_asks`.
- Listing text: each side keeps its printed shape through `detail` (/review adds file_line, gate and class), pinned by `test_review_fix_script.py::ReviewFixScriptTest::test_asks_are_jumped_listed_and_logged_with_their_outcomes` and the /code open-phase indent tests.
- Working folder of the jump: /code runs it in the repo, /review in the current folder, as before. No test pinned either rule.

## Evidence

judgment: a smell review of the review scripts found the two copies and their drift.

## Result

Printed ask listings are unchanged on both sides. A multi-location or bare-path ask no longer moves the editor.

## Watch

None.

## Back-out

Revert this change's commit.
