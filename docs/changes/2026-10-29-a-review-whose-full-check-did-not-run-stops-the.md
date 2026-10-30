---
type: "Change"
change_type: "fixed"
title: "A review whose full check did not run stops the /code phase"
description: "A converged review whose full check timed out, was scoped or could not be read now stops the /code phase instead of marking it done; a pass, a CI repo, a repo with no check, an expected-red check, a check-command error and an environment gap still finish it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T22:08:50-05:00"}
seq: 300
kind: "fix"
components: ["script/code-step", "script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_a_converged_or_deferred_review_whose_full_check_did_not_run_stops_the_phase_naming_the_result"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `full_check.is_check_not_run` is true for a `not run` result the check owed: a timeout, or a scoped or unresolved
  command. Every other `not run` result still finishes the phase.
- `/code` stops a converged or deferred review on such a result with stop kind `check-not-run`. The stop names the
  result, the check command and the fix, then says to run `review-again`, which accepts the new stop.
- The unverified stop and this one share one stop helper and one "add a Quality check line" fix.

## Evidence

- The stop step read only an `unverified` result. A review whose check timed out or was scoped converged, and the
  phase end marked the phase done with no full check behind it.
- This reverses the timeout half of 2026-10-27-a-repo-whose-full-suite-runs-in-ci-gets-only-the.md, which let a
  timeout pass in every repo. The environment gap stays a pass, as
  2026-10-27-the-full-check-runs-under-the-repos-pinned-python.md set.

## Result

- The named test failed before the change and passes after it. The not-owed results still finish the phase.

## Watch

None: no intake number counts phases finished with a check that did not run.

## Back-out

Revert the commit.
