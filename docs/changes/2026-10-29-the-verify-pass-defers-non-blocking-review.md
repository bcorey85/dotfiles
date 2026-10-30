---
type: "Change"
change_type: "changed"
title: "The verify pass defers non-blocking review findings and goes on to the plan check"
description: "When the branch-wide review in /verify-branch reports no blocker, its fix findings are logged as deferred and the run goes on to the plan-verifier, so the pass no longer stops on each fresh set of small findings; a blocker still stops the pass until it is fixed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T20:23:55-05:00"}
seq: 295
kind: "fix"
components: ["script/verify-prep", "script/verify-log", "skill/verify-branch", "shared/closing-phases"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_the_review_step_defers_non_blocking_fixes_and_fixes_only_a_blocker"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `verify-prep`'s review step says: with no blocker finding, do not fix. Log each fix finding as `deferred` and go on
  to the plan-verifier. With a blocker, route the findings through `/review`, fix them, then log.
- `verify-log review` refuses a blocker finding logged as anything but `fixed` or `skipped_fp`, so a blocker cannot
  be deferred or left as an ask. A bold `**[blocker]**` counts too: verify-log and the review loop's parsers share
  one blocker-tag pattern in `script_utils`.
- With no blocker, each `ask` finding is still listed to the user.
- The verify-branch skill and the closing phases' Verify pass say the same: the pass needs no open blocker, not a
  clean review.

## Evidence

- The verify pass stopped on every run that had non-blocking findings and did not reach the plan-verifier. Each fix
  changed the tree, so the next run reran the whole branch review, and a fresh reviewer found a new set of small
  findings.

## Result

- The named test and the deferred-blocker refusal test failed before the change and pass after it. A finding is a
  blocker when its `desc` starts with `[blocker]`, any case, the code-reviewer's own tag. A non-blocking fix finding
  logged `deferred` lets the next prep report the review as ran.

## Watch

None: no intake number counts verify-pass stops. The share of branch-exit findings logged `deferred` rises by design,
so it reads the rule being followed, not a gain.

## Back-out

Revert the commit.
