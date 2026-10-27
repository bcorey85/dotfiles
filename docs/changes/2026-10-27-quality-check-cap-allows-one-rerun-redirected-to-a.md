---
type: "Change"
title: "quality-check-cap allows one rerun redirected to a file after a run cut by tail, head or grep"
description: "When a check's last run was piped through tail, head or grep, the cap allows one rerun with its output sent to a file, and the deny names that exact form."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T08:07:26-05:00"}
seq: 3
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_the_cut_deny_names_a_form_the_cap_then_allows"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The post event marks a run as cut when its output went into `tail`, `head` or `grep` and was not first saved to a
  file (`tee <file>` or `> <file>`).
- After a cut run, the cap allows one rerun of the same check that sends its stdout to a file. A rerun that does not
  keep its output is still denied.
- The deny after a cut run names the exact form to run: the check as typed, its `cd <dir> &&`, wrapper and
  assignment prefixes kept, with ` > /tmp/check.log 2>&1` appended.
- The plain deny's suggested form no longer reads as a second allowed run.

## Evidence

- Queue item `quality-check-cap-blocks-the-first-full-look-at-a`: an agent-evals session ran a lint through `tail -2`
  and saw only `Found 2 errors.`. The cap then denied the bare lint and the log-redirected form its own message
  named, so the session could not read the errors it had to fix.
- The new tests fail on the base commit and pass after.

## Result

- `tests/scripts/test_quality_check_cap.py` passes (91 tests); ruff passes on the changed files.

## Watch

—

## Back-out

Revert the commit.
