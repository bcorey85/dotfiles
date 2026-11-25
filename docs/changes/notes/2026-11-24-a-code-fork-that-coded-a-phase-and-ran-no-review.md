---
type: "Change"
change_type: "fixed"
title: "a code fork that coded a phase and ran no review is sent back at SubagentStop and denied at SubagentHandback"
description: "A /code fork that dispatched a coder for a phase and ended with no review and no stop.md write after the dispatch is sent back once at SubagentStop, or denied at SubagentHandback."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T14:10:39-06:00"}
seq: 4
kind: "fix"
components: ["script/coder-gate", "script/staged-claim-gate", "script/shell-command", "script/shell-command-words", "script/fork-children", "script/announced-step", "script/script-utils", "script/fork-review", "script/user-prompts", "script/human-turn-lookup", "script/loop-transcript"]
evidence: ["real transcript"]
watches: []
test: "tests/scripts/test_fork_review_gate.py::ForkReviewGateTests::test_incident_fork_with_a_coder_and_no_review_is_sent_back"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

lib/fork_review.py reads a /code fork's own transcript in phase segments. A segment with a coder dispatch needs a review start then a wait for the review after it, or a stop.md write. staged_claim_gate.py sends a fork that fails this back once at SubagentStop; the code-fork branch of coder_gate.py hook denies its SubagentHandback. `script_call_arguments` in shell_command_words.py now reads `shell_code` (heredoc bodies and comments cut), with `step_words` for text shlex cannot read; this also changes how coder_gate.py `is_stale_prose_check` reads a command.

## Evidence

A real fork dispatched a coder, waited on it, ran git status and ended with a final text reply and no review.

## Result

The sweep over /code forks started on or after 2026-10-31T21:31 sends back 96 of 1192 (8.05%); hand-read send-backs are true misses or forks that ended mid coder wait. The close pass moved the background-launch reader (`turn_launched_background`) from script_utils into user_prompts, made human_turn_lookup read its lines through `transcript_record`, and tightened the stop.md write read to redirects and `tee` targets. It also added `script_utils.makes_own_calls`: fork_review `read_line`, fork_children `scan_fork_commands` and user_prompts `turn_launched_background` skip api-request-blob records. A blob repeat of an earlier background launch no longer counts as a launch for announced_step, and fork_children's run window no longer opens on a final blob, and a trailing non-message record (attachment, system, progress) no longer closes it. fork_children `scan_fork_commands` reads a review start through `script_call_arguments`, so a heredoc body or a quoted echo that only names code_review_start.py no longer opens the loop's run window. `variable_assignments` reads each step on its own, so a stop-file path assigned before a step shlex cannot read still names the stop write.

## Watch

How many /code forks are sent back, and whether any send-back is a gate gap.

## Back-out

Remove the fork_review calls from staged_claim_gate.py and coder_gate.py.
