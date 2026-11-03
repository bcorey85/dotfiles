---
type: "Change"
change_type: "added"
title: "A session start deletes the temp folders of sessions idle a day or more"
description: "Old session scratchpads no longer pile up until the per-user temp quota fills and every shell call fails."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T16:39:20-06:00"}
seq: 10
kind: "fix"
components: ["script/sweep-scratchpads"]
evidence: ["incident"]
watches: []
test: "tests/scripts/test_sweep_scratchpads.py::SweepScratchpadsTest::test_a_session_folder_untouched_for_two_days_is_deleted"
asked: ""
proof: []
unmeasured: ""
---

## Change

New `scripts/tools/sweep_scratchpads.py`, a SessionStart hook on `startup`, run async. It deletes each `<temp>/claude-<uid>/<project>/<session id>/` folder whose newest entry is over 24 hours old. It keeps the current session's folder and anything not named for a session id, and never follows a link. `<temp>` is `CLAUDE_CODE_TMPDIR` when set, else the system temp folder. It fails open: an error goes to stderr and the hook exits 0.

It is a new process, not folded into an existing SessionStart hook. Every existing Python SessionStart hook runs synchronously and does an unrelated job (rules injection, skip-hooks warning, calibration guard). Folding the walk into one of them adds its time to every session start; as its own async hook it costs the start nothing.

No bench-arm free-space check: no one script owns arm starts.

## Evidence

On 2026-11-02 four session scratchpads held 7.9 GB of the 8.3 GB under `/tmp/claude-1000`, the per-user quota filled, and three bench reviews and one probe lost every Bash call. Nothing deleted a scratchpad when its session ended. This machine holds 635 session folders and about 20,000 entries under that root.

## Result

Timing on a synthetic root the size of this machine's (640 session folders, about 20,000 entries, worst case where the walk visits every folder and deletes nothing), median of 15: bare `python3 -c pass` 26 ms, the sweep through `hook-python` 221 ms. It runs async, so the session start does not wait on it.

## Watch

None: no intake number reads temp-folder size.

## Back-out

Remove the SessionStart entry from `settings.json` and delete the script and its test.
