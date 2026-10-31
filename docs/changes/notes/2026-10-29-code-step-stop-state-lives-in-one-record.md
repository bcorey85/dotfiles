---
type: "Change"
change_type: "changed"
title: "Code-step stop state lives in one record"
description: "The /code step keeps every stop fact in state['stop'] and its baselines in state['snapshot'], an old state file migrates on read, and the unread packet key and duplicate asksApplied are gone."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T12:56:12-05:00"}
seq: 266
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_state_file_in_the_old_stop_format_resumes_the_coder_as_before"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_core.py`: `state["stop"] = {kind, at, agentId, waitAt}` replaces `stopReason`, `resumableCoderAt`,
  `resumableCoderId`, `resumableReview` and `resumeWaitAt`; the stage stays `stopped`. `set_stop`, `clear_stop`,
  `stop_kind` and their siblings are how a new stop is written and how most code reads its kind; `code_step.py` and
  `code_step_start.py` still read `state["stop"]` fields directly in a few places. `state["snapshot"]` holds the
  plan-edit, asks and follow-up baselines.
- `migrate_old_state` runs in `read_state_file`, so a state file written before this change resumes as it did. Precedence is coder, then review, then reason, as the old readers saw them.
- The unread `state["packet"]` write and the duplicate `asksApplied` flag are gone. `dispatchAt` and
  `reviewScriptPid` stay their own keys: each outlives or predates a stop.
- `code_step_review_stops.py` writes its tool-fault, blocker, unverified-check and cap-reached stops through
  `set_stop`, so no code writes an old key.

## Evidence

- Seven loose keys described one stop, written and popped at about thirty sites, so a site that set one and missed
  another left a half-stopped state.

## Result

- The named test resumes a coder from an old-format state file, and
  `ResumeTest::test_a_state_file_with_the_old_resumable_review_key_resumes_the_review_as_before` resumes a review.
- Review caught one regression in the draft (`ask_the_user` cleared a false-clean stop kind); a test now pins it.

## Watch

—

## Back-out

Revert the commit. State files written in the new shape then lose their stop record.
