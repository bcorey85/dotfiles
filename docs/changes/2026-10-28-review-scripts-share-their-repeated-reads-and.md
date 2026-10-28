---
type: "Change"
title: "Review scripts share their repeated reads and messages"
description: "The review scripts drop hand-written copies of a session-row read, a skill-file update, a keep-dirty sentence, a deny line and an error translation, with no behavior change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T07:21:11-05:00"}
seq: 176
kind: "user-rule"
components: ["script/review-fix", "script/handback", "script/deferred-push-check", "script/verify-common", "script/open-child-gate"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-28: lets fan out some workers - see if there are some ways to refactor / simplify code and review scripts"
proof: []
unmeasured: ""
---

## Change

- review_fix.py: one helper updates the per-skill misses and waits files; one constant holds the keep-dirty sentence;
  `load_fix_state` reads through `read_state`; the verb list is the handlers dict; `stop_for_unreviewed` has one tail.
- handback.py: one `session_rows` accessor replaces eight copies of the session-file read and its kind and agent
  filters. `deny_line` is gone; the hook calls `script_utils.pre_tool_use_deny`, as open_child_gate.py now does.
- deferred_push_check.py: `git_subcommand` returns only the subcommand. Its own reader and git runner stay, so a
  git timeout or an unreadable findings file still silences the hook.
- verify_common.py: `manual_items` and `moved_phase_notes` use the existing `raising_verify_error` wrapper.

## Evidence

- A read-only survey of the review scripts listed each duplication; the existing tests pin the behavior, and none
  changed.

## Result

- Net -16 lines across five files. Printed text, exit codes and stored rows are unchanged.

## Watch

No watch: a refactor with no behavior change.

## Back-out

Revert the commit.
