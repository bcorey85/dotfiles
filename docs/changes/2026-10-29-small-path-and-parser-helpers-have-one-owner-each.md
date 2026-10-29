---
type: "Change"
title: "Small path and parser helpers have one owner each"
description: "Duplicated path builders, status and JSONL parsers, deny output and review-again text in the code and review scripts now call one owner each, and plan section scans skip code fences."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T11:19:02-05:00"}
seq: 258
kind: "fix"
components: ["script/code-step", "script/coder-gate", "script/coder-packet", "script/plan-format", "script/script-utils", "script/review-commit-gate", "script/review-fix", "script/review-loop-script", "script/deferred-push-check", "script/batch-reads-nudge", "script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_format.py::PlanFileEditTest::test_a_section_heading_inside_a_code_fence_does_not_end_the_deviations_section"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New owners in `script_utils`: `git_path()` (the coder-gate, code-step state, review-fix and the replaced-criteria folder dirs),
  `subagent_transcript_path()` (three copies, including `batch_reads_nudge.py`) and `top_level_sections()`, which
  finds `## ` lines outside code fences for `coder_packet.phase_bounds` and `plan_format.append_deviation`.
- `code_step_core.state_file()` owns the `state.json` path; `reviewed_tree.review_gate_dir()` owns the review-gate
  dir and now reads `Path.home()`; `RESUME_LINE` is built from `INSTALLED_COMMAND`; the seven review-again lines use
  `REVIEW_AGAIN_INVOKE` and `REVIEW_SAME_DIFF_AGAIN_LINE` with their text unchanged; `PATH_IN_BACKTICKS` lives in
  `plan_format`.
- `split_decide_args` uses `pop_option`, `review_loop_script.scope()` uses `worktree_snapshot.status_codes`,
  `deferred_push_check` uses `read_jsonl`, and `check_dispatch` uses `pre_tool_use_deny`.
- Not merged: `reviewed_tree.fingerprint` and `verify_common.branch_fingerprint` hash different bases in different
  formats, so one owner would change stored fingerprints. The `FullCheckSteps` mixin already has one user. Ask code
  is untouched.

## Evidence

- The complexity and smell review of the code and review scripts found each listed helper built or parsed in two to
  seven places.

## Result

- The named test fails before (a fenced `## ` line ended the deviations section) and passes after.
- Side effects of the shared owners: `scope()` reads `git status -z`, so paths with spaces and renames parse right;
  `deferred_push_check` reads a missing findings file as no rows.

## Watch

—

## Back-out

Revert the commit.
