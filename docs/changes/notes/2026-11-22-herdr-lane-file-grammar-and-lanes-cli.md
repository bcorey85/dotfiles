---
type: "Change"
change_type: "added"
title: "herdr lane file grammar and lanes CLI"
description: "Each herdr lane gets one JSON file under herdr-lanes with a single grammar in lib/lane_entries.py, a lanes.py command for every bash caller, and a registry lookup by name."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T16:52:37-06:00"}
seq: 22
kind: "fix"
components: ["script/lanes", "shared/lane-entries"]
evidence: ["tests", "review rounds"]
watches: []
test: "tests/scripts/test_lanes.py::test_every_verb_prints_its_json_and_a_lane_round_trips"
asked: ""
proof: []
unmeasured: "New infrastructure with no caller yet: no intake number reads it. A later phase wires the callers."
---

## Change

- New lane file `<state>/herdr-lanes/<name>.json`, where `<state>` is `${XDG_STATE_HOME:-$HOME/.local/state}`. Fields:
  `name`, `worktree`, `main_checkout`, `branch`, `brief`, `session_id`, `reports_to`, `started_at`. The one grammar is
  `lib/lane_entries.py` (`read_entry`); an unknown or missing key, a wrong type, a name that differs from the file
  stem, or invalid JSON raises `LaneFileError` naming file and field. Every write holds `lanes.lock` for 10 s and
  writes atomically. `add_entry` refuses a live entry and replaces one whose worktree folder is gone.
- New `tools/lanes.py` with verbs `add`, `set-session`, `remove`, `get` (also `--containing PATH`), `list` and
  `check`, JSON on stdout. Exit 0 on success, 1 when `add` meets a live entry or `set-session` / `remove` find no
  entry, 2 on a bad lane file or a lock held too long (stderr names file, field and expected form).
- `session_registry.row_for_name(name)` returns the first live row with that name, else `None`.
- `script_utils.xdg_state_home` is the one reader of the state folder.

## Evidence

- `bash tests/run.sh`: 5279 tests, 0 failed.
- Four review rounds.
- Tests: `tests/scripts/test_lane_entries.py` (library under a temp state folder, each bad shape),
  `tests/scripts/test_lanes.py` (CLI as a subprocess, every verb, exit codes, held lock) and
  `tests/scripts/test_session_registry.py` (`row_for_name`: found, dead pid skipped, absent).

## Result

Applied. No callers use the lane file yet.

## Watch

None: see `unmeasured`.

## Back-out

Revert the commit.
