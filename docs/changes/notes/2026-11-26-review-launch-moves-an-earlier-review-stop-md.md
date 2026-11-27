---
type: "Change"
change_type: "fixed"
title: "review launch moves an earlier review-stop.md aside"
description: "A review launch moves an earlier review-stop.md to review-stop.prev.md, so the review fork writes a new file the Write tool accepts."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T06:33:08-06:00"}
seq: 12
kind: "fix"
components: ["script/review-launch", "script/code-relay", "script/phase-start"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_a_launch_moves_an_earlier_review_stop_aside_so_the_fork_writes_a_new_file"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/review_launch.py` `command_launch` moves the `review-stop.md` of the starting directory's run folder (where the fork writes its stop and the relay reads it, also under `--repo`) to `review-stop.prev.md` right after it finds the repo, before every stop that comes after the repo check (a missing session id or a repo outside a work tree stops first and leaves the file in place), through the new shared `script_utils.move_aside` (moved out of `code/phase_start.py`, which now calls it). `lib/stop_file_names.py` adds `PREVIOUS_REVIEW_STOP_FILE`, `MOVED_ASIDE_STOPS` and `PREVIOUS_STOP_FILES` (built from `MOVED_ASIDE_STOPS`). `code/code_relay.py` reads both previous-stop files when it picks the newest stop, and exits 1 when the newest is a moved-aside file, since the run wrote no new stop, except a moved-aside stop that was bounced and not yet relayed: that one relays once with exit 0 (`relay_bounced_stop` takes an `origin` parameter, and only an `origin` of `stop.md` gets the resume path and a session record).

## Evidence

A resumed review fork has a fresh read state, so its Write of `review-stop.md` failed as "not read yet" when an earlier run had left one.

## Result

The launch test and `test_a_launch_that_stops_still_moves_the_earlier_review_stop_aside` fail before the change and pass after. `test_code_relay.py::RelayTest::test_a_review_stop_moved_aside_by_review_launch_is_not_replaced_by_an_older_stop` shows the relay does not relay an older stop past a moved one.

## Watch

Read the next review fork's stop write for a "not read yet" refusal.

## Back-out

Drop the `move_aside` call in `command_launch`, the three new names in `stop_file_names.py` and the `origin` parameter of `relay_bounced_stop` with its `origin == STOP_FILE` gate; restore the `stop.name == PREVIOUS_STOP_FILE` branch in `code_relay.relay` with its `STOP_FILE` stamp and the "phase_start moved aside" text; restore `code_relay.newest_stop` to `(*STOP_FILES, PREVIOUS_STOP_FILE)` and its import list; `move_aside` can stay shared.
