---
type: "Change"
change_type: "fixed"
title: "code_wait returns within 150 s and writes each reviewer's report as it lands"
description: "code_wait.py waits at most 150 s per call (under the harness's 180 s auto-background), takes `review [<agent id> <report file>]...` pairs and writes each finished reviewer's report on its own, exits 1 naming an agent that finished with no report, and exits 2 on an argument that is not an agent id or a requested report file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T23:38:00-06:00"}
seq: 6
kind: "fix"
components: ["script/code-wait", "script/reviewer-dispatch", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_wait.py::ReviewerRequestTest::test_ids_joined_into_one_word_stop_loudly"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_wait.py`: `WAIT_SECONDS` 540 → 150. `agent <id>` loses `--report-file`. `review` takes `<agent id> <report file>` pairs: each poll writes the report of every named reviewer that has finished, and the wait returns on a new unanswered request, a reviewer that finished with no report (exit 1, named, with the re-dispatch line), or the loop's end. A word that is not `a` plus 16 hex digits, an odd word count, or a report file no request names exits 2 with the usage text. `reviewer_dispatch.py` gains `all_requests`; `pending_requests` filters it. `skills/code/SKILL.md` drops the 600000 timeout and names the pair form, each word written out.

## Evidence

judgment: transcripts show 342 Bash calls moved to the background at 180 s, which led forks to wrap the wait in variables, loops and functions. zsh keeps an unquoted `$VAR` as one word, so the id never matched a transcript and the wait printed `Still working` forever (50 of 50 direct calls answered correctly). The serial per-agent wait held finished reports until the slowest agent ended, and the loop timed out. The tests named fail on the base commit and pass after.

## Result

`test_code_wait.py` 22 of 22, `test_reviewer_dispatch.py` 11 of 11, `test_code_review_start.py` 14 of 14 pass; lint clean.

## Watch

—

## Back-out

Revert `code_wait.py`, `all_requests` in `reviewer_dispatch.py`, the SKILL.md lines and the tests.
