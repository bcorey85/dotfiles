---
type: "Change"
change_type: "fixed"
title: "Every toolkit gate refusal opens with its [gate] tag"
description: "Every PreToolUse deny of a toolkit gate now opens with [<script name with hyphens>], so the work intake credits each refusal to the gate that made it instead of printing it as other <tool> hook."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T21:38:49-06:00"}
seq: 6
kind: "fix"
components: ["script/hook-input", "script/rg-path-gate", "script/coder-gate", "script/wait-loop-gate", "script/handback", "script/quality-check-cap", "script/inline-interpreter-hint", "script/spec-budget-gate", "script/fork-write-scope", "script/open-child-gate", "script/fork-children", "script/agent-model-guard"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_hook_input.py::RefusalReasonTest::test_a_deny_reason_opens_with_the_gate_tag"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/hook_input.py` gains `refusal_reason`: a deny reason that does not open with `[` gets `[<hook_name()>] ` in front. `decision_line` applies it to every deny, so `emit_decision("deny", ...)` tags the refusal. The duplicate `script_utils.pre_tool_use_deny` is gone; coder_gate, handback_hook, open_child_gate and fork_children call `hook_input.emit_decision`. wait_loop_gate, spec_budget_gate and inline_interpreter_hint drop their own hand-built deny JSON for it (spec_budget_gate's JSON had no escaping). rg_path_gate tags the reason in its decision dict. fork_write_scope and spec_budget_gate move from a `name:` opening to `[name]`. agent-model-guard.sh opens its four reasons with `[agent-model-guard]`. quality_check_cap's and inline_interpreter_hint's memory-cap denials, which sent the shared memory_cap_scope text untagged, are now tagged too. `lib/unread_overwrite.py`'s deny opens with `[unread-overwrite]` in place of `unread-overwrite:`, so fork_write_scope keeps it credited to that check.

The three CB security gates are untouched: their rule denials carry `[rule]` tags already, and their fallback denials are written up in `~/agent-evals/WORK-SECURITY-HOOKS.md`.

## Evidence

Census of this machine's transcripts over 60 days (dotfiles and agent-evals projects left out), counting error tool results that `work_review_queue.denial` maps to "other ... hook": 4438 Bash, 601 with no listed tool (SubagentHandback), 51 Write, 34 Agent, 12 Read, 2 Edit. The largest groups opened with rg_path_gate's text (1106), coder_gate's hand-back and whole-suite texts (370, 305), and the memory-cap texts.

## Result

Each touched gate's test file asserts its deny opens with its tag. The full suite passes apart from two comment-bloat-gate tests in `test_review_fixes.py`, which fail on the base commit too.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
