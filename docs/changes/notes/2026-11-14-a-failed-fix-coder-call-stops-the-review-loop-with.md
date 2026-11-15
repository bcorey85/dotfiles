---
type: "Change"
change_type: "fixed"
title: "A failed fix coder call stops the review loop with its findings kept, and the brief stays small"
description: "A fix coder call that fails (for example Prompt is too long) now stops the loop as critical-blocker with the findings still in findings_remaining, and the /code skill never dispatches a coder on them itself. The coder brief folds long file lists by directory and cuts each issue, with the full text in files under the loop's out folder."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-14T12:00:00-06:00"}
seq: 3
kind: "fix"
components: ["script/review-loop", "skill/code"]
evidence: ["transcript read"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_coder_call_that_fails_stops_loudly_and_keeps_the_findings_in_the_packet"
asked: ""
proof: []
unmeasured: "No run measures how often a brief passed the prompt limit."
---

## Change

`review_loop_prompts.coder_prompt` lists at most 50 issues and 50 small items, each cut to 240 characters, and folds any
file list over 40 paths by directory with `lib/path_summary.collapse_paths`. Held and later-phase paths that share a
directory with an in-scope file are never folded. When no depth folds the list to 40 entries or fewer even then, the
brief lists the first 40 entries (those paths first) and `and N more`, and the full list is in the named file. When an
issue or small item is longer than 240 characters once its whitespace is collapsed, or more than 50 are given, the full
texts go to `<out>/coder-briefs/<call>/`, and so does any path list over 40 paths; the brief names each file it writes.
`LoopRun.repair` turns a failed coder call into
`CoderFailedError`, keeps the findings in `open_fixes` and the changed files in `files_touched`, and `run_loop` stops
as `critical-blocker` with a blocker that says the findings were not all applied,
must not be applied outside the review loop, and that the review reruns once the cause is fixed. The `/code` skill's `critical-blocker` route adds: never
dispatch a coder on the packet's findings yourself.

## Evidence

transcript read: a real run's fix coder failed with Prompt is too long on a 754 KB brief (6812 held files), the packet
lost its findings, and the /code fork then fixed them in an unreviewed coder pass.

## Result

The new tests in `test_review_loop_script.py` and `test_path_summary.py` cover each part.

## Watch

None: a script fix with a fixed outcome. The loop now exits 0 on a failed coder call, where it used to exit 1 with a
crash packet.

## Back-out

Restore the inline file lists in `coder_prompt`, let `repair` re-raise the call error, and drop the sentence from the
`/code` route.
