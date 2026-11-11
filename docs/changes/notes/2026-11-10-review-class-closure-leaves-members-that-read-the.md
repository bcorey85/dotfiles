---
type: "Change"
change_type: "fixed"
title: "Class closure leaves members that read the value for another purpose and names them in the hand-back"
description: "The review loop's class-closure check now says what each member reads the value for before it calls the member open, lists members with another purpose under a new left_alone reply field, and carries those members in a left_alone packet field that the hand-back renders, even when the receipt is missing."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-10T18:49:00-06:00"}
seq: 9
kind: "fix"
components: ["script/review-loop-script", "script/handback", "script/review-loop-packet", "script/review-loop-findings", "script/reply-json"]
evidence: ["review-class-closure-sweeps-readers-without"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_repaired_class_packet_carries_the_members_left_alone"
asked: ""
proof: []
unmeasured: "No meter run; the user ruled ship on 2026-11-10 in session agent-evals-5e."
---

## Change

- `review/review_loop_closure.py`: `CLOSURE_RULES` adds a purpose check, the reply gains a `left_alone` list, and the recovery parser for a reply that will not decode keeps that list.
- `review/review_loop_closure.py`: new `ClosureState` holds the receipt, the open classes and the left-alone list.
- `review/review_loop_script.py`: `class_closure_pass` stores the list in `ClosureState.left_alone`, which the outcome builder writes to the `left_alone` packet field, so a missing receipt keeps it. `LoopRun` holds one `closure` field in place of the receipt and open-classes fields.
- `review/review_loop_packet.py`: the packet message writes `left_alone`, and the empty outcome carries it.
- `review/handback.py`: `left_alone` is a packet key, a list key and a string-list key, and the hand-back renders it.
- `review/review_loop_findings.py`: `reply_with_one_retry` takes a `problem` check, which returns a reason string. A closure reply whose `open` or `left_alone` is not a list of non-blank strings is rejected with that reason, retried once, and a second bad reply raises. The retry note now reads "could not be used" in place of "could not be parsed".
- `lib/script_utils.py`: new `is_nonblank_string_list`, which the closure check and `read_findings` share.
- `review/review_loop_prompt_file.py`: `read_findings` uses `is_nonblank_string_list`.
- New `lib/reply_json.py` holds the two readers of JSON inside a model reply: the closure parser's `list_after_last_key` and `last_json_object`, moved from `review_loop_findings.py`. Their tests are in `tests/scripts/test_reply_json.py`.

## Evidence

The closure check listed readers of a value as open when they read it for another purpose, and the repair coder then edited them.

## Result

Tests cover the closed, held, repaired and still-open packets, a reply without `left_alone`, and a raw-quote reply that keeps it. A malformed `open` or `left_alone` list is retried with a prompt that names the rejected key, and a second malformed reply raises with the same text.

## Watch

None: the change is pinned by tests.

## Back-out

The change spans `44bab1ba`, `2d7b96f0` and `c16f9d73`, which adds the `problem` check to `review_loop_findings.py`. Restore each closure file to its state before `44bab1ba` (`git checkout 44bab1ba^ -- <file>`); `2d7b96f0` also holds unrelated detach and plan edits, which stay. Restore these files:

- `claude/.claude/scripts/review/handback.py`
- `claude/.claude/scripts/review/review_loop_closure.py`
- `claude/.claude/scripts/review/review_loop_findings.py` (its `problem` check comes from `c16f9d73`)
- `claude/.claude/scripts/review/review_loop_packet.py`
- `claude/.claude/scripts/review/review_loop_script.py`
- `tests/scripts/test_handback.py`
- `tests/scripts/test_review_loop_closure.py`
- `tests/scripts/test_review_loop_script.py` (keep `test_a_fix_first_run_rejects_a_blank_finding_text`)

Then `git rm` `claude/.claude/scripts/lib/reply_json.py` and `tests/scripts/test_reply_json.py`, and drop `reply_json.py` from the lib lists in `docs/toolkit-script-rules.md`: the restored `review_loop_findings.py` and `test_review_loop_script.py` hold `last_json_object` and its test again.

`claude/.claude/scripts/lib/script_utils.py` and `claude/.claude/scripts/review/review_loop_prompt_file.py` stay, because `read_findings` uses the helper.

Separately, revert the Phase 3 edits in `docs/plans/coder-worktree-fixes/plan.md`, `docs/changes/changelog.md` and `docs/changes/index.md`.
