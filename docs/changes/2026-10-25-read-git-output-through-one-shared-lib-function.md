---
type: "Change"
title: "Read git output through one shared lib function"
description: "Six toolkit scripts and one lib helper each ran git through their own git_output copy; they now all call script_utils.git_output, which drops stderr, turns path quoting off, keeps non-UTF-8 names and takes an optional timeout."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T15:50:43-05:00"}
seq: 4
kind: "user-rule"
components: ["script/script-utils", "script/code-step", "script/coder-gate", "script/coder-packet", "script/review-fix", "script/review-commit-gate", "script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-25: queue the merge (of the seven git_output copies in toolkit scripts), then: do it"
proof: []
unmeasured: ""
---

## Change

`lib/script_utils.py` gets `git_output(cwd, *args, timeout=None)`. It runs `git -c core.quotepath=false <args>` in cwd
with stdin closed. It returns stdout without trailing newlines, decoded as `os.fsdecode` does, or None when git fails,
is missing, or runs past the timeout.

These now call it and keep no copy of their own: `code/code_step_core.py` (and `code_step.py` and
`code_step_boundary.py`, which imported its copy), `code/coder_gate.py`, `code/coder_packet.py`,
`review/review_fix.py`, `review/review_commit_gate.py`, `gates/quality_check_cap.py`, and
`script_utils.inside_git_work_tree`. The two hook gates pass their own timeouts (3 and 5 seconds).

Behavior that moved for some callers:

- `review_fix` joined stderr to the answer on success, so a git warning became part of a branch name or a path. It
  now gets stdout only.
- `coder_packet` crashed with a traceback when the plan was outside a repo. It now stops with a message.
- `coder_gate`, `coder_packet` and `review_fix` got quoted, escaped paths for non-ASCII names. They now get the
  name as it is.
- `quality_check_cap` hashed raw bytes with trailing newlines. It now hashes the same text without them, so a run
  recorded before this change counts as changed once.
- `review_commit_gate` decoded bad bytes to U+FFFD. They now round-trip.

## Evidence

The user asked for the merge after the stale-prose script's review found it was the seventh copy. A survey found six
copies on master with six different bodies. The seventh, in the stale-prose script, is on no branch yet and moves to
the lib function when it lands.

## Result

One function, eight callers. `bash tests/run.sh`: 2050 tests in 54 files, 0 failed, ruff clean. New tests in
`tests/scripts/test_script_utils.py::GitOutputTest` and
`tests/scripts/test_coder_packet.py::CoderPacketTest::test_a_plan_outside_any_git_repository_stops_with_a_message`.

## Watch

None. No intake number reads how a script runs git.

## Back-out

Revert the commit. Each script gets its own copy back.
